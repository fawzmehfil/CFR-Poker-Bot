use std::fs;
use std::process::Command;
use std::time::Instant;

const CHECK: u8 = 0;
const BET: u8 = 1;
const CALL: u8 = 2;
const RAISE: u8 = 3;
const FOLD: u8 = 4;
const MAX_RAISES: u8 = 2;
const BET_SIZES: [i16; 2] = [2, 4];

#[derive(Clone, Copy)]
struct Lcg {
    state: u64,
}

impl Lcg {
    fn new(seed: u64) -> Self {
        Self { state: seed }
    }

    #[inline]
    fn next_u64(&mut self) -> u64 {
        self.state = self
            .state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        self.state
    }

    #[inline]
    fn next_usize(&mut self, upper: usize) -> usize {
        (self.next_u64() as usize) % upper
    }
}

#[derive(Clone, Copy)]
struct FastState {
    deal: [u8; 3],
    round: u8,
    current: u8,
    contributions: [i16; 2],
    bets: [i16; 2],
    raises: u8,
    history: [[u8; 8]; 2],
    history_len: [u8; 2],
    terminal: bool,
    folded: u8,
}

impl FastState {
    #[inline]
    fn new(deal: [u8; 3]) -> Self {
        Self {
            deal,
            round: 0,
            current: 0,
            contributions: [1, 1],
            bets: [0, 0],
            raises: 0,
            history: [[255; 8]; 2],
            history_len: [0, 0],
            terminal: false,
            folded: 2,
        }
    }

    #[inline]
    fn pot(&self) -> i16 {
        self.contributions[0] + self.contributions[1]
    }

    #[inline]
    fn rank(card: u8) -> u8 {
        card / 2
    }

    #[inline]
    fn to_call(&self, player: usize) -> i16 {
        self.bets[0].max(self.bets[1]) - self.bets[player]
    }

    #[inline]
    fn legal_actions(&self, out: &mut [u8; 3]) -> usize {
        if self.terminal {
            return 0;
        }
        let player = self.current as usize;
        if self.to_call(player) > 0 {
            out[0] = FOLD;
            out[1] = CALL;
            if self.raises < MAX_RAISES {
                out[2] = RAISE;
                3
            } else {
                2
            }
        } else {
            out[0] = CHECK;
            if self.raises < MAX_RAISES {
                out[1] = BET;
                2
            } else {
                1
            }
        }
    }

    #[inline]
    fn apply(&mut self, action: u8) {
        let round = self.round as usize;
        let player = self.current as usize;
        let len = self.history_len[round] as usize;
        self.history[round][len] = action;
        self.history_len[round] += 1;

        match action {
            FOLD => {
                self.terminal = true;
                self.folded = self.current;
            }
            CALL => {
                let call = self.to_call(player);
                self.contributions[player] += call;
                self.bets[player] += call;
                self.after_closed_betting();
            }
            BET | RAISE => {
                let amount = self.to_call(player) + BET_SIZES[round];
                self.contributions[player] += amount;
                self.bets[player] += amount;
                self.raises += 1;
                self.current = 1 - self.current;
            }
            CHECK => {
                let hlen = self.history_len[round] as usize;
                if hlen >= 2 && self.history[round][hlen - 2] == CHECK && self.history[round][hlen - 1] == CHECK {
                    self.after_closed_betting();
                } else {
                    self.current = 1 - self.current;
                }
            }
            _ => unreachable!("benchmark only applies legal actions"),
        }
    }

    #[inline]
    fn after_closed_betting(&mut self) {
        if self.round == 0 {
            self.round = 1;
            self.current = 0;
            self.bets = [0, 0];
            self.raises = 0;
        } else {
            self.terminal = true;
        }
    }

    #[inline]
    fn showdown_winner(&self) -> u8 {
        let p0 = Self::rank(self.deal[0]);
        let p1 = Self::rank(self.deal[1]);
        let public = Self::rank(self.deal[2]);
        let pair0 = p0 == public;
        let pair1 = p1 == public;
        if pair0 != pair1 {
            return if pair0 { 0 } else { 1 };
        }
        if p0 == p1 {
            return 2;
        }
        if p0 > p1 { 0 } else { 1 }
    }

    #[inline]
    fn utility(&self, player: usize) -> f64 {
        let winner = if self.folded != 2 {
            1 - self.folded
        } else {
            self.showdown_winner()
        };
        if winner == 2 {
            self.pot() as f64 / 2.0 - self.contributions[player] as f64
        } else if winner as usize == player {
            (self.pot() - self.contributions[player]) as f64
        } else {
            -(self.contributions[player] as f64)
        }
    }

    fn trace_summary(&self) -> String {
        format!(
            "round={};current={};terminal={};pot={};u0={:.1};legal={}",
            self.round,
            self.current,
            self.terminal,
            self.pot(),
            if self.terminal { self.utility(0) } else { 0.0 },
            action_list(self)
        )
    }
}

#[inline]
fn random_deal(rng: &mut Lcg) -> [u8; 3] {
    let mut cards = [0, 1, 2, 3, 4, 5];
    for i in (1..cards.len()).rev() {
        let j = rng.next_usize(i + 1);
        cards.swap(i, j);
    }
    [cards[0], cards[1], cards[2]]
}

#[inline]
fn simulate_hand(rng: &mut Lcg) -> (f64, u64) {
    let mut state = FastState::new(random_deal(rng));
    let mut legal = [0; 3];
    let mut transitions = 0;
    while !state.terminal {
        let n = state.legal_actions(&mut legal);
        let action = legal[rng.next_usize(n)];
        state.apply(action);
        transitions += 1;
    }
    (state.utility(0), transitions)
}

fn action_token(action: u8) -> &'static str {
    match action {
        CHECK => "k",
        BET => "b",
        CALL => "c",
        RAISE => "r",
        FOLD => "f",
        _ => "?",
    }
}

fn action_list(state: &FastState) -> String {
    let mut legal = [0; 3];
    let n = state.legal_actions(&mut legal);
    (0..n).map(|idx| action_token(legal[idx])).collect::<Vec<_>>().join(",")
}

fn rust_trace() -> String {
    let mut fold = FastState::new([4, 2, 0]);
    fold.apply(BET);
    fold.apply(FOLD);
    let mut showdown = FastState::new([4, 2, 0]);
    showdown.apply(CHECK);
    showdown.apply(CHECK);
    showdown.apply(CHECK);
    showdown.apply(CHECK);
    format!("fold:{}|showdown:{}", fold.trace_summary(), showdown.trace_summary())
}

fn python_trace_and_speed(py_hands: usize) -> (bool, String, f64) {
    let code = format!(
        r#"
import json, random, sys, time
sys.path.insert(0, '..')
from leduc_cfr.poker.leduc import LeducState, random_deal

def legal_text(s):
    return ','.join(s.legal_actions())

fold = LeducState(deal=("K1", "Q1", "J1")).apply("b").apply("f")
showdown = LeducState(deal=("K1", "Q1", "J1")).apply("k").apply("k").apply("k").apply("k")
trace = (
    f"fold:round={{fold.round_index}};current={{fold.current_player}};terminal={{str(fold.terminal).lower()}};"
    f"pot={{fold.pot}};u0={{fold.utility(0):.1f}};legal={{legal_text(fold)}}|"
    f"showdown:round={{showdown.round_index}};current={{showdown.current_player}};"
    f"terminal={{str(showdown.terminal).lower()}};pot={{showdown.pot}};u0={{showdown.utility(0):.1f}};"
    f"legal={{legal_text(showdown)}}"
)
rng = random.Random(7)
utility = 0.0
start = time.perf_counter()
for _ in range({py_hands}):
    state = LeducState(deal=random_deal(rng))
    while not state.terminal:
        state = state.apply(rng.choice(state.legal_actions()))
    utility += state.utility(0)
elapsed = time.perf_counter() - start
print(json.dumps({{"trace": trace, "hands_per_sec": {py_hands} / elapsed, "avg_utility_p0": utility / {py_hands}}}))
"#
    );
    let output = Command::new("../.venv/bin/python")
        .arg("-c")
        .arg(code)
        .current_dir(".")
        .output();

    let Ok(output) = output else {
        return (false, "python_unavailable".to_string(), 0.0);
    };
    if !output.status.success() {
        return (false, String::from_utf8_lossy(&output.stderr).to_string(), 0.0);
    }
    let text = String::from_utf8_lossy(&output.stdout);
    let trace = extract_json_string(&text, "trace").unwrap_or_default();
    let hands_per_sec = extract_json_number(&text, "hands_per_sec").unwrap_or(0.0);
    (trace == rust_trace(), trace, hands_per_sec)
}

fn extract_json_string(text: &str, key: &str) -> Option<String> {
    let marker = format!("\"{key}\": \"");
    let start = text.find(&marker)? + marker.len();
    let rest = &text[start..];
    let end = rest.find('"')?;
    Some(rest[..end].to_string())
}

fn extract_json_number(text: &str, key: &str) -> Option<f64> {
    let marker = format!("\"{key}\": ");
    let start = text.find(&marker)? + marker.len();
    let rest = &text[start..];
    let end = rest.find([',', '}']).unwrap_or(rest.len());
    rest[..end].trim().parse().ok()
}

fn main() {
    let hands = std::env::args()
        .nth(1)
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(1_000_000);
    let transitions_target = hands * 8;
    let py_hands = (hands / 20).clamp(10_000, 100_000);

    let mut rng = Lcg::new(7);
    let start = Instant::now();
    let mut utility_sum = 0.0;
    let mut transition_count = 0_u64;
    for _ in 0..hands {
        let (utility, transitions) = simulate_hand(&mut rng);
        utility_sum += utility;
        transition_count += transitions;
    }
    let random_elapsed = start.elapsed().as_secs_f64();
    let random_hands_per_sec = hands as f64 / random_elapsed;

    let mut rng = Lcg::new(11);
    let start = Instant::now();
    for _ in 0..hands {
        let _ = simulate_hand(&mut rng);
    }
    let rollout_elapsed = start.elapsed().as_secs_f64();
    let terminal_rollouts_per_sec = hands as f64 / rollout_elapsed;

    let mut rng = Lcg::new(13);
    let mut state = FastState::new(random_deal(&mut rng));
    let mut legal = [0; 3];
    let start = Instant::now();
    for _ in 0..transitions_target {
        if state.terminal {
            state = FastState::new(random_deal(&mut rng));
        }
        let n = state.legal_actions(&mut legal);
        let action = legal[rng.next_usize(n)];
        state.apply(action);
    }
    let transition_elapsed = start.elapsed().as_secs_f64();
    let state_transitions_per_sec = transitions_target as f64 / transition_elapsed;

    let (correctness_passed, python_trace, python_hands_per_sec) = python_trace_and_speed(py_hands);
    let speedup = if python_hands_per_sec > 0.0 {
        random_hands_per_sec / python_hands_per_sec
    } else {
        0.0
    };

    let json = format!(
        concat!(
            "{{\n",
            "  \"hands\": {hands},\n",
            "  \"python_hands\": {py_hands},\n",
            "  \"random_hands_per_sec\": {random_hands_per_sec:.2},\n",
            "  \"terminal_rollouts_per_sec\": {terminal_rollouts_per_sec:.2},\n",
            "  \"state_transitions_per_sec\": {state_transitions_per_sec:.2},\n",
            "  \"python_hands_per_sec\": {python_hands_per_sec:.2},\n",
            "  \"rust_hands_per_sec\": {random_hands_per_sec:.2},\n",
            "  \"speedup_factor\": {speedup:.2},\n",
            "  \"avg_utility_p0\": {avg_utility:.6},\n",
            "  \"avg_transitions_per_hand\": {avg_transitions:.4},\n",
            "  \"correctness_comparison_passed\": {correctness_passed},\n",
            "  \"rust_trace\": \"{rust_trace}\",\n",
            "  \"python_trace\": \"{python_trace}\"\n",
            "}}\n"
        ),
        hands = hands,
        py_hands = py_hands,
        random_hands_per_sec = random_hands_per_sec,
        terminal_rollouts_per_sec = terminal_rollouts_per_sec,
        state_transitions_per_sec = state_transitions_per_sec,
        python_hands_per_sec = python_hands_per_sec,
        speedup = speedup,
        avg_utility = utility_sum / hands as f64,
        avg_transitions = transition_count as f64 / hands as f64,
        correctness_passed = correctness_passed,
        rust_trace = rust_trace(),
        python_trace = python_trace.replace('"', "\\\""),
    );

    fs::create_dir_all("../data").expect("create data directory");
    fs::write("../data/rust_benchmark.json", &json).expect("write rust benchmark json");
    let markdown = format!(
        concat!(
            "# Performance Summary\n\n",
            "| Metric | Value |\n",
            "|---|---:|\n",
            "| Rust random hands/sec | {random_hands_per_sec:.2} |\n",
            "| Rust terminal rollouts/sec | {terminal_rollouts_per_sec:.2} |\n",
            "| Rust state transitions/sec | {state_transitions_per_sec:.2} |\n",
            "| Python hands/sec | {python_hands_per_sec:.2} |\n",
            "| Speedup factor | {speedup:.2}x |\n",
            "| Correctness comparison | {correctness} |\n"
        ),
        random_hands_per_sec = random_hands_per_sec,
        terminal_rollouts_per_sec = terminal_rollouts_per_sec,
        state_transitions_per_sec = state_transitions_per_sec,
        python_hands_per_sec = python_hands_per_sec,
        speedup = speedup,
        correctness = if correctness_passed { "passed" } else { "failed" },
    );
    fs::write("../data/performance_summary.md", markdown).expect("write performance summary");

    println!("random_hands_per_sec: {random_hands_per_sec:.2}");
    println!("terminal_rollouts_per_sec: {terminal_rollouts_per_sec:.2}");
    println!("state_transitions_per_sec: {state_transitions_per_sec:.2}");
    println!("python_hands_per_sec: {python_hands_per_sec:.2}");
    println!("rust_hands_per_sec: {random_hands_per_sec:.2}");
    println!("speedup_factor: {speedup:.2}");
    println!("correctness_comparison_passed: {correctness_passed}");
    println!("wrote ../data/rust_benchmark.json");
    println!("wrote ../data/performance_summary.md");
}
