use std::time::Instant;

use leduc_engine::{deal_from_indices, Action, LeducState};

struct Lcg {
    state: u64,
}

impl Lcg {
    fn new(seed: u64) -> Self {
        Self { state: seed }
    }

    fn next_u64(&mut self) -> u64 {
        self.state = self
            .state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        self.state
    }

    fn next_usize(&mut self, upper: usize) -> usize {
        (self.next_u64() as usize) % upper
    }
}

fn random_deal(rng: &mut Lcg) -> [usize; 3] {
    let mut cards = [0, 1, 2, 3, 4, 5];
    for i in (1..cards.len()).rev() {
        let j = rng.next_usize(i + 1);
        cards.swap(i, j);
    }
    [cards[0], cards[1], cards[2]]
}

fn simulate_hand(rng: &mut Lcg) -> f64 {
    let deal = deal_from_indices(random_deal(rng)).expect("valid shuffled deal");
    let mut state = LeducState::new(deal).expect("valid state");
    while !state.terminal {
        let legal = state.legal_actions();
        let action: Action = legal[rng.next_usize(legal.len())];
        state = state.apply(action).expect("random legal action should apply");
    }
    state.utility(0).expect("terminal utility")
}

fn main() {
    let hands = std::env::args()
        .nth(1)
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(1_000_000);
    let mut rng = Lcg::new(7);
    let start = Instant::now();
    let mut utility_sum = 0.0;
    for _ in 0..hands {
        utility_sum += simulate_hand(&mut rng);
    }
    let elapsed = start.elapsed().as_secs_f64();
    let hands_per_sec = hands as f64 / elapsed;
    println!("hands: {hands}");
    println!("elapsed_sec: {elapsed:.6}");
    println!("hands_per_sec: {hands_per_sec:.2}");
    println!("avg_utility_p0: {:.6}", utility_sum / hands as f64);
}

