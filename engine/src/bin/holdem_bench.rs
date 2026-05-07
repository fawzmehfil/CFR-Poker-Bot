use leduc_engine::holdem::{evaluate_hand, Action, Card, HoldemState, Lcg};
use std::time::Instant;

fn main() {
    let args = std::env::args().skip(1).collect::<Vec<_>>();
    if args.first().map(String::as_str) == Some("--trace") {
        let cards = args
            .get(1)
            .expect("--trace requires nine comma-separated cards");
        let actions = args.get(2).map(String::as_str).unwrap_or("");
        println!("{}", trace_from_cards(cards, actions).expect("build Hold'em trace"));
        return;
    }
    if args.first().map(String::as_str) == Some("--seed-trace") {
        let seed = args
            .get(1)
            .expect("--seed-trace requires a seed")
            .parse::<u64>()
            .expect("seed must be an integer");
        let actions = args.get(2).map(String::as_str).unwrap_or("");
        println!("{}", trace_from_seed(seed, actions).expect("build seeded Hold'em trace"));
        return;
    }

    let hands = args
        .first()
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(100_000);
    let seed = args
        .get(1)
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(7);

    let mut rng = Lcg::new(seed);
    let start = Instant::now();
    for _ in 0..hands {
        let mut state = HoldemState::from_seed(rng.next_u64());
        while !state.terminal {
            let legal = state.legal_actions();
            let action = legal[rng.next_usize(legal.len())];
            state = state.apply(action).expect("random legal action applies");
        }
        let _ = state.utility(0).expect("terminal utility");
    }
    let hands_elapsed = start.elapsed().as_secs_f64();

    let evals = hands * 20;
    let mut rng = Lcg::new(seed + 1);
    let start = Instant::now();
    for _ in 0..evals {
        let state = HoldemState::from_seed(rng.next_u64());
        let mut cards = Vec::with_capacity(7);
        cards.extend(state.hole_cards[0]);
        cards.extend(state.deck_cards.iter().take(5).copied());
        let _ = evaluate_hand(&cards).expect("evaluate seven cards");
    }
    let eval_elapsed = start.elapsed().as_secs_f64();

    let transitions = hands * 12;
    let mut rng = Lcg::new(seed + 2);
    let mut state = HoldemState::from_seed(rng.next_u64());
    let start = Instant::now();
    for _ in 0..transitions {
        if state.terminal {
            state = HoldemState::from_seed(rng.next_u64());
        }
        let legal = state.legal_actions();
        let action = legal[rng.next_usize(legal.len())];
        state = state.apply(action).expect("random legal transition applies");
    }
    let transition_elapsed = start.elapsed().as_secs_f64();

    println!(
        concat!(
            "{{",
            "\"hands\":{hands},",
            "\"seed\":{seed},",
            "\"random_hands_per_sec\":{hands_per_sec:.2},",
            "\"state_transitions_per_sec\":{transitions_per_sec:.2},",
            "\"showdown_evaluations_per_sec\":{evals_per_sec:.2}",
            "}}"
        ),
        hands = hands,
        seed = seed,
        hands_per_sec = hands as f64 / hands_elapsed,
        transitions_per_sec = transitions as f64 / transition_elapsed,
        evals_per_sec = evals as f64 / eval_elapsed,
    );
}

fn trace_from_cards(cards_text: &str, actions_text: &str) -> Result<String, String> {
    let cards = cards_text
        .split(',')
        .map(Card::parse)
        .collect::<Result<Vec<_>, _>>()?;
    if cards.len() < 9 {
        return Err("trace requires at least nine cards: p0a,p1a,p0b,p1b,board...".to_string());
    }
    let mut state = HoldemState::new(cards[4..].to_vec(), [[cards[0], cards[2]], [cards[1], cards[3]]]);
    for action_text in actions_text.split(',').filter(|value| !value.is_empty()) {
        state = state.apply(Action::parse(action_text)?)?;
    }
    Ok(state.trace_summary())
}

fn trace_from_seed(seed: u64, actions_text: &str) -> Result<String, String> {
    let mut state = HoldemState::from_seed(seed);
    for action_text in actions_text.split(',').filter(|value| !value.is_empty()) {
        state = state.apply(Action::parse(action_text)?)?;
    }
    Ok(state.trace_summary())
}
