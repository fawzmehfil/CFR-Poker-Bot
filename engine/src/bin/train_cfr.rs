use std::collections::HashMap;
use std::fs;
use std::time::Instant;

use leduc_engine::{Action, LeducState, CARDS};

const ACTIONS: [Action; 5] = [
    Action::Check,
    Action::Bet,
    Action::Call,
    Action::Raise,
    Action::Fold,
];

#[derive(Clone)]
struct InfoSet {
    regret_sum: [f64; 5],
    strategy_sum: [f64; 5],
    seen: [bool; 5],
}

impl InfoSet {
    fn new() -> Self {
        Self {
            regret_sum: [0.0; 5],
            strategy_sum: [0.0; 5],
            seen: [false; 5],
        }
    }

    fn strategy(&self, legal: &[Action]) -> Vec<f64> {
        let positives: Vec<f64> = legal
            .iter()
            .map(|a| self.regret_sum[action_idx(*a)].max(0.0))
            .collect();
        let total: f64 = positives.iter().sum();
        if total <= 0.0 {
            vec![1.0 / legal.len() as f64; legal.len()]
        } else {
            positives.iter().map(|v| v / total).collect()
        }
    }

    fn average_strategy(&self) -> Vec<(Action, f64)> {
        let total: f64 = self
            .strategy_sum
            .iter()
            .enumerate()
            .filter(|(idx, _)| self.seen[*idx])
            .map(|(_, value)| value.max(0.0))
            .sum();
        let actions: Vec<Action> = ACTIONS
            .iter()
            .copied()
            .filter(|action| self.seen[action_idx(*action)])
            .collect();
        if actions.is_empty() {
            return vec![(Action::Bet, 0.5), (Action::Check, 0.5)];
        }
        if total <= 0.0 {
            let prob = 1.0 / actions.len() as f64;
            return actions.into_iter().map(|action| (action, prob)).collect();
        }
        actions
            .into_iter()
            .map(|action| {
                let idx = action_idx(action);
                (action, self.strategy_sum[idx].max(0.0) / total)
            })
            .collect()
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum SelectionMode {
    BestGap,
    BestHeuristic,
    Balanced,
    Final,
}

impl SelectionMode {
    fn parse(value: &str) -> Self {
        match value {
            "best_gap" => Self::BestGap,
            "best_heuristic" => Self::BestHeuristic,
            "balanced" => Self::Balanced,
            "final" => Self::Final,
            other => {
                panic!(
                    "unsupported --selection {other}; expected best_gap, best_heuristic, balanced, or final"
                )
            }
        }
    }
}

#[derive(Clone)]
struct Checkpoint {
    iteration: usize,
    utility: f64,
    gap: f64,
    random_avg_utility: f64,
    heuristic_avg_utility: f64,
    info_sets: HashMap<String, InfoSet>,
}

#[derive(Clone, Copy)]
enum OpponentPolicy {
    Random,
    Heuristic,
}

struct LcgRng {
    state: u64,
}

impl LcgRng {
    fn new(seed: u64) -> Self {
        Self {
            state: seed ^ 0x9e37_79b9_7f4a_7c15,
        }
    }

    fn next_u64(&mut self) -> u64 {
        self.state = self
            .state
            .wrapping_mul(6_364_136_223_846_793_005)
            .wrapping_add(1);
        self.state
    }

    fn next_usize(&mut self, upper: usize) -> usize {
        (self.next_u64() as usize) % upper
    }

    fn next_f64(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 / ((1u64 << 53) as f64)
    }
}

struct Trainer {
    info_sets: HashMap<String, InfoSet>,
    cfr_plus: bool,
    deals: Vec<[leduc_engine::Card; 3]>,
}

impl Trainer {
    fn new(cfr_plus: bool) -> Self {
        let mut deals = Vec::new();
        for i in 0..CARDS.len() {
            for j in 0..CARDS.len() {
                for k in 0..CARDS.len() {
                    if i != j && i != k && j != k {
                        deals.push([CARDS[i], CARDS[j], CARDS[k]]);
                    }
                }
            }
        }
        Self {
            info_sets: HashMap::new(),
            cfr_plus,
            deals,
        }
    }

    fn train(
        &mut self,
        iterations: usize,
        eval_interval: usize,
        selection: SelectionMode,
        selection_hands: usize,
        seed: u64,
    ) -> (Vec<f64>, Checkpoint) {
        let mut utilities = Vec::with_capacity(iterations);
        let mut checkpoints = Vec::new();
        for iteration in 1..=iterations {
            let mut total = 0.0;
            for deal_idx in 0..self.deals.len() {
                let state = LeducState::new(self.deals[deal_idx]).expect("valid deal");
                total += self.cfr(state, 1.0, 1.0);
            }
            let utility = total / self.deals.len() as f64;
            utilities.push(utility);
            if iteration == 1 || iteration == iterations || iteration % eval_interval == 0 {
                let gap = nash_gap_upper_bound(&self.info_sets, &self.deals);
                let (random_avg_utility, heuristic_avg_utility) = if matches!(
                    selection,
                    SelectionMode::BestHeuristic | SelectionMode::Balanced
                ) && selection_hands > 0
                {
                    (
                        head_to_head(
                            &self.info_sets,
                            &self.deals,
                            OpponentPolicy::Random,
                            selection_hands,
                            seed,
                        ),
                        head_to_head(
                            &self.info_sets,
                            &self.deals,
                            OpponentPolicy::Heuristic,
                            selection_hands,
                            seed + 5,
                        ),
                    )
                } else {
                    (0.0, 0.0)
                };
                let checkpoint = Checkpoint {
                    iteration,
                    utility,
                    gap,
                    random_avg_utility,
                    heuristic_avg_utility,
                    info_sets: self.info_sets.clone(),
                };
                checkpoints.push(checkpoint);
            }
        }
        let selected = select_checkpoint(&checkpoints, selection);
        self.info_sets = selected.info_sets.clone();
        (utilities, selected)
    }

    fn cfr(&mut self, state: LeducState, reach0: f64, reach1: f64) -> f64 {
        if state.terminal {
            return state.utility(0).expect("terminal utility");
        }

        let player = state.current_player;
        let legal = state.legal_actions();
        let key = state.info_set_key(player);
        let strategy = {
            let info = self
                .info_sets
                .entry(key.clone())
                .or_insert_with(InfoSet::new);
            let strategy = info.strategy(&legal);
            let reach = if player == 0 { reach0 } else { reach1 };
            for (action, prob) in legal.iter().zip(strategy.iter()) {
                let idx = action_idx(*action);
                info.seen[idx] = true;
                info.strategy_sum[idx] += reach * prob;
            }
            strategy
        };

        let mut child_values = vec![0.0; legal.len()];
        let mut node_value = 0.0;
        for (idx, action) in legal.iter().enumerate() {
            let next_state = state.apply(*action).expect("legal action");
            child_values[idx] = if player == 0 {
                self.cfr(next_state, reach0 * strategy[idx], reach1)
            } else {
                self.cfr(next_state, reach0, reach1 * strategy[idx])
            };
            node_value += strategy[idx] * child_values[idx];
        }

        let info = self.info_sets.entry(key).or_insert_with(InfoSet::new);
        for (idx, action) in legal.iter().enumerate() {
            let regret = if player == 0 {
                child_values[idx] - node_value
            } else {
                node_value - child_values[idx]
            };
            let weighted = if player == 0 {
                reach1 * regret
            } else {
                reach0 * regret
            };
            let action_index = action_idx(*action);
            let updated = info.regret_sum[action_index] + weighted;
            info.regret_sum[action_index] = if self.cfr_plus {
                updated.max(0.0)
            } else {
                updated
            };
        }

        node_value
    }

    fn save_strategy(&self, path: &str) {
        let mut keys: Vec<&String> = self.info_sets.keys().collect();
        keys.sort();
        let mut out = String::from("{\n  \"strategies\": {\n");
        for (key_pos, key) in keys.iter().enumerate() {
            out.push_str(&format!("    \"{}\": {{", key));
            let avg = self.info_sets[*key].average_strategy();
            for (idx, (action, prob)) in avg.iter().enumerate() {
                if idx > 0 {
                    out.push_str(", ");
                }
                out.push_str(&format!("\"{}\": {}", action.token(), format_float(*prob)));
            }
            out.push('}');
            if key_pos + 1 < keys.len() {
                out.push(',');
            }
            out.push('\n');
        }
        out.push_str("  }\n}\n");
        if let Some(parent) = std::path::Path::new(path).parent() {
            fs::create_dir_all(parent).expect("create output directory");
        }
        fs::write(path, out).expect("write strategy");
    }
}

fn select_checkpoint(checkpoints: &[Checkpoint], selection: SelectionMode) -> Checkpoint {
    match selection {
        SelectionMode::Final => checkpoints.last().expect("checkpoint").clone(),
        SelectionMode::BestGap => checkpoints
            .iter()
            .min_by(|a, b| a.gap.total_cmp(&b.gap))
            .expect("checkpoint")
            .clone(),
        SelectionMode::BestHeuristic => checkpoints
            .iter()
            .max_by(|a, b| {
                a.heuristic_avg_utility
                    .total_cmp(&b.heuristic_avg_utility)
                    .then_with(|| b.gap.total_cmp(&a.gap))
                    .then_with(|| a.random_avg_utility.total_cmp(&b.random_avg_utility))
            })
            .expect("checkpoint")
            .clone(),
        SelectionMode::Balanced => {
            let gaps: Vec<f64> = checkpoints.iter().map(|point| point.gap).collect();
            let random_utils: Vec<f64> = checkpoints
                .iter()
                .map(|point| point.random_avg_utility)
                .collect();
            let heuristic_utils: Vec<f64> = checkpoints
                .iter()
                .map(|point| point.heuristic_avg_utility)
                .collect();
            checkpoints
                .iter()
                .max_by(|a, b| {
                    balanced_score(a, &gaps, &random_utils, &heuristic_utils)
                        .total_cmp(&balanced_score(b, &gaps, &random_utils, &heuristic_utils))
                        .then_with(|| b.gap.total_cmp(&a.gap))
                })
                .expect("checkpoint")
                .clone()
        }
    }
}

fn balanced_score(
    checkpoint: &Checkpoint,
    gaps: &[f64],
    random_utils: &[f64],
    heuristic_utils: &[f64],
) -> f64 {
    0.45 * normalize(checkpoint.gap, gaps, true)
        + 0.20 * normalize(checkpoint.random_avg_utility, random_utils, false)
        + 0.35 * normalize(checkpoint.heuristic_avg_utility, heuristic_utils, false)
}

fn normalize(value: f64, values: &[f64], invert: bool) -> f64 {
    let lo = values.iter().copied().fold(f64::INFINITY, f64::min);
    let hi = values.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    if (hi - lo).abs() <= f64::EPSILON {
        return 1.0;
    }
    let score = (value - lo) / (hi - lo);
    if invert {
        1.0 - score
    } else {
        score
    }
}

fn action_probs(
    info_sets: &HashMap<String, InfoSet>,
    state: &LeducState,
    player: usize,
    legal: &[Action],
) -> Vec<f64> {
    let key = state.info_set_key(player);
    let Some(info) = info_sets.get(&key) else {
        return vec![1.0 / legal.len() as f64; legal.len()];
    };
    let avg = info.average_strategy();
    let mut values = Vec::with_capacity(legal.len());
    for action in legal {
        let prob = avg
            .iter()
            .find(|(avg_action, _)| avg_action == action)
            .map(|(_, prob)| (*prob).max(0.0))
            .unwrap_or(0.0);
        values.push(prob);
    }
    let total: f64 = values.iter().sum();
    if total <= 0.0 {
        vec![1.0 / legal.len() as f64; legal.len()]
    } else {
        values.into_iter().map(|value| value / total).collect()
    }
}

fn best_response_value(
    info_sets: &HashMap<String, InfoSet>,
    state: LeducState,
    br_player: usize,
) -> f64 {
    if state.terminal {
        return state.utility(br_player).expect("terminal utility");
    }
    let legal = state.legal_actions();
    if state.current_player == br_player {
        legal
            .iter()
            .map(|action| {
                best_response_value(
                    info_sets,
                    state.apply(*action).expect("legal action"),
                    br_player,
                )
            })
            .fold(f64::NEG_INFINITY, f64::max)
    } else {
        let probs = action_probs(info_sets, &state, state.current_player, &legal);
        legal
            .iter()
            .zip(probs.iter())
            .map(|(action, prob)| {
                prob * best_response_value(
                    info_sets,
                    state.apply(*action).expect("legal action"),
                    br_player,
                )
            })
            .sum()
    }
}

fn nash_gap_upper_bound(
    info_sets: &HashMap<String, InfoSet>,
    deals: &[[leduc_engine::Card; 3]],
) -> f64 {
    let p0: f64 = deals
        .iter()
        .map(|deal| best_response_value(info_sets, LeducState::new(*deal).expect("valid deal"), 0))
        .sum::<f64>()
        / deals.len() as f64;
    let p1: f64 = deals
        .iter()
        .map(|deal| best_response_value(info_sets, LeducState::new(*deal).expect("valid deal"), 1))
        .sum::<f64>()
        / deals.len() as f64;
    (p0 + p1) / 2.0
}

fn head_to_head(
    info_sets: &HashMap<String, InfoSet>,
    deals: &[[leduc_engine::Card; 3]],
    opponent: OpponentPolicy,
    hands: usize,
    seed: u64,
) -> f64 {
    let mut rng = LcgRng::new(seed);
    let mut total = 0.0;
    for hand_index in 0..hands {
        let cfr_player = hand_index % 2;
        let deal = deals[rng.next_usize(deals.len())];
        let mut state = LeducState::new(deal).expect("valid deal");
        while !state.terminal {
            let legal = state.legal_actions();
            let action = if state.current_player == cfr_player {
                sample_profile_action(info_sets, &state, state.current_player, &legal, &mut rng)
            } else {
                match opponent {
                    OpponentPolicy::Random => legal[rng.next_usize(legal.len())],
                    OpponentPolicy::Heuristic => {
                        heuristic_action(&state, state.current_player, &legal)
                    }
                }
            };
            state = state.apply(action).expect("legal action");
        }
        total += state.utility(cfr_player).expect("terminal utility");
    }
    if hands == 0 {
        0.0
    } else {
        total / hands as f64
    }
}

fn sample_profile_action(
    info_sets: &HashMap<String, InfoSet>,
    state: &LeducState,
    player: usize,
    legal: &[Action],
    rng: &mut LcgRng,
) -> Action {
    let probs = action_probs(info_sets, state, player, legal);
    let roll = rng.next_f64();
    let mut acc = 0.0;
    for (action, prob) in legal.iter().zip(probs.iter()) {
        acc += prob;
        if roll <= acc {
            return *action;
        }
    }
    *legal.last().expect("legal action")
}

fn heuristic_action(state: &LeducState, player: usize, legal: &[Action]) -> Action {
    let private_rank = state.private_cards()[player].rank;
    let public_rank = if state.round_index == 1 {
        Some(state.public_card().rank)
    } else {
        None
    };
    let has_pair = public_rank == Some(private_rank);
    let is_high_card = private_rank.value() == 2;
    let is_low_card = private_rank.value() == 0;
    let to_call = state.to_call(player);

    if to_call == 0 {
        if legal.contains(&Action::Bet) && (has_pair || (state.round_index == 0 && is_high_card)) {
            return Action::Bet;
        }
        return Action::Check;
    }

    if legal.contains(&Action::Raise) && has_pair {
        return Action::Raise;
    }
    if legal.contains(&Action::Call) && (has_pair || is_high_card || to_call <= 2) {
        return Action::Call;
    }
    if legal.contains(&Action::Fold) && is_low_card {
        return Action::Fold;
    }
    if legal.contains(&Action::Call) {
        Action::Call
    } else {
        legal[0]
    }
}

fn action_idx(action: Action) -> usize {
    match action {
        Action::Check => 0,
        Action::Bet => 1,
        Action::Call => 2,
        Action::Raise => 3,
        Action::Fold => 4,
    }
}

fn format_float(value: f64) -> String {
    if value == 0.0 {
        "0.0".to_string()
    } else if value == 1.0 {
        "1.0".to_string()
    } else {
        format!("{:.17}", value)
            .trim_end_matches('0')
            .trim_end_matches('.')
            .to_string()
    }
}

fn arg_value(args: &[String], name: &str, default: &str) -> String {
    args.windows(2)
        .find(|window| window[0] == name)
        .map(|window| window[1].clone())
        .unwrap_or_else(|| default.to_string())
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let iterations = arg_value(&args, "--iterations", "1000")
        .parse::<usize>()
        .expect("iterations must be integer");
    let seed = arg_value(&args, "--seed", "0")
        .parse::<u64>()
        .expect("seed must be integer");
    let out = arg_value(&args, "--out", "../data/cfr_strategy_rust.json");
    let cfr_plus = args.iter().any(|arg| arg == "--cfr-plus");
    let eval_interval = arg_value(&args, "--eval-interval", "100")
        .parse::<usize>()
        .expect("eval interval must be integer")
        .max(1);
    let selection = SelectionMode::parse(&arg_value(&args, "--selection", "best_gap"));
    let selection_hands = arg_value(&args, "--selection-hands", "1000")
        .parse::<usize>()
        .expect("selection hands must be integer");

    let start = Instant::now();
    let mut trainer = Trainer::new(cfr_plus);
    let (utilities, selected) =
        trainer.train(iterations, eval_interval, selection, selection_hands, seed);
    trainer.save_strategy(&out);
    let elapsed = start.elapsed().as_secs_f64();
    let root_traversals = iterations * trainer.deals.len();
    let traversals_per_sec = root_traversals as f64 / elapsed;

    println!("seed: {seed}");
    println!("iterations: {iterations}");
    println!("cfr_plus: {cfr_plus}");
    println!("selection: {:?}", selection);
    println!("eval_interval: {eval_interval}");
    println!("selection_hands: {selection_hands}");
    println!("selected_iteration: {}", selected.iteration);
    println!("selected_nash_gap_upper_bound: {:.12}", selected.gap);
    println!(
        "selected_vs_random_avg_utility: {:.12}",
        selected.random_avg_utility
    );
    println!(
        "selected_vs_heuristic_avg_utility: {:.12}",
        selected.heuristic_avg_utility
    );
    println!("selected_avg_utility_p0: {:.12}", selected.utility);
    println!("infosets: {}", trainer.info_sets.len());
    println!(
        "final_avg_utility_p0: {:.12}",
        utilities.last().copied().unwrap_or(0.0)
    );
    println!("runtime_sec: {:.6}", elapsed);
    println!("root_traversals: {root_traversals}");
    println!("root_traversals_per_sec: {:.2}", traversals_per_sec);
    println!("saved_strategy: {out}");
}
