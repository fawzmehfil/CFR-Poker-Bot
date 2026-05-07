use std::fmt;

pub const STARTING_STACK: i32 = 100;
pub const SMALL_BLIND: i32 = 1;
pub const BIG_BLIND: i32 = 2;
pub const MAX_RAISES_PER_STREET: u8 = 4;

#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub struct Card {
    pub rank: u8,
    pub suit: u8,
}

impl Card {
    pub const fn new(rank: u8, suit: u8) -> Self {
        Self { rank, suit }
    }

    pub fn parse(text: &str) -> Result<Self, String> {
        let bytes = text.as_bytes();
        if bytes.len() != 2 {
            return Err(format!("invalid card: {text}"));
        }
        let rank = match bytes[0] as char {
            '2'..='9' => bytes[0] - b'0',
            'T' => 10,
            'J' => 11,
            'Q' => 12,
            'K' => 13,
            'A' => 14,
            _ => return Err(format!("invalid card rank: {text}")),
        };
        let suit = match bytes[1] as char {
            'c' => 0,
            'd' => 1,
            'h' => 2,
            's' => 3,
            _ => return Err(format!("invalid card suit: {text}")),
        };
        Ok(Self { rank, suit })
    }
}

impl fmt::Display for Card {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let rank = match self.rank {
            2..=9 => char::from(b'0' + self.rank),
            10 => 'T',
            11 => 'J',
            12 => 'Q',
            13 => 'K',
            14 => 'A',
            _ => '?',
        };
        let suit = match self.suit {
            0 => 'c',
            1 => 'd',
            2 => 'h',
            3 => 's',
            _ => '?',
        };
        write!(f, "{rank}{suit}")
    }
}

pub fn deck() -> Vec<Card> {
    let mut cards = Vec::with_capacity(52);
    for rank in 2..=14 {
        for suit in 0..=3 {
            cards.push(Card::new(rank, suit));
        }
    }
    cards
}

#[derive(Clone, Copy)]
pub struct Lcg {
    state: u64,
}

impl Lcg {
    pub fn new(seed: u64) -> Self {
        Self { state: seed }
    }

    pub fn next_u64(&mut self) -> u64 {
        self.state = self
            .state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        self.state
    }

    pub fn next_usize(&mut self, upper: usize) -> usize {
        (self.next_u64() as usize) % upper
    }
}

pub fn shuffled_deck(seed: u64) -> Vec<Card> {
    let mut cards = deck();
    let mut rng = Lcg::new(seed);
    for i in (1..cards.len()).rev() {
        let j = rng.next_usize(i + 1);
        cards.swap(i, j);
    }
    cards
}

pub type HandScore = [u8; 6];

pub fn evaluate_hand(cards: &[Card]) -> Result<HandScore, String> {
    if !(5..=7).contains(&cards.len()) {
        return Err("Hold'em hand evaluation requires five to seven cards".to_string());
    }
    let mut best = [0; 6];
    for a in 0..cards.len() - 4 {
        for b in a + 1..cards.len() - 3 {
            for c in b + 1..cards.len() - 2 {
                for d in c + 1..cards.len() - 1 {
                    for e in d + 1..cards.len() {
                        let score = evaluate_five([cards[a], cards[b], cards[c], cards[d], cards[e]]);
                        if score > best {
                            best = score;
                        }
                    }
                }
            }
        }
    }
    Ok(best)
}

fn evaluate_five(cards: [Card; 5]) -> HandScore {
    let mut ranks = [0_u8; 5];
    for (idx, card) in cards.iter().enumerate() {
        ranks[idx] = card.rank;
    }
    ranks.sort_by(|a, b| b.cmp(a));

    let flush = cards.iter().all(|card| card.suit == cards[0].suit);
    let straight = straight_high(&ranks);
    let mut counts = Vec::new();
    for rank in 2..=14 {
        let count = ranks.iter().filter(|value| **value == rank).count() as u8;
        if count > 0 {
            counts.push((count, rank));
        }
    }
    counts.sort_by(|a, b| b.cmp(a));

    if flush {
        if let Some(high) = straight {
            return [8, high, 0, 0, 0, 0];
        }
    }
    if counts[0].0 == 4 {
        let quad = counts[0].1;
        let kicker = *ranks.iter().find(|rank| **rank != quad).unwrap();
        return [7, quad, kicker, 0, 0, 0];
    }
    if counts[0].0 == 3 && counts[1].0 == 2 {
        return [6, counts[0].1, counts[1].1, 0, 0, 0];
    }
    if flush {
        return [5, ranks[0], ranks[1], ranks[2], ranks[3], ranks[4]];
    }
    if let Some(high) = straight {
        return [4, high, 0, 0, 0, 0];
    }
    if counts[0].0 == 3 {
        let trip = counts[0].1;
        let kickers: Vec<u8> = ranks.iter().copied().filter(|rank| *rank != trip).collect();
        return [3, trip, kickers[0], kickers[1], 0, 0];
    }
    if counts[0].0 == 2 && counts[1].0 == 2 {
        let high_pair = counts[0].1.max(counts[1].1);
        let low_pair = counts[0].1.min(counts[1].1);
        let kicker = *ranks
            .iter()
            .find(|rank| **rank != high_pair && **rank != low_pair)
            .unwrap();
        return [2, high_pair, low_pair, kicker, 0, 0];
    }
    if counts[0].0 == 2 {
        let pair = counts[0].1;
        let kickers: Vec<u8> = ranks.iter().copied().filter(|rank| *rank != pair).collect();
        return [1, pair, kickers[0], kickers[1], kickers[2], 0];
    }
    [0, ranks[0], ranks[1], ranks[2], ranks[3], ranks[4]]
}

fn straight_high(ranks: &[u8; 5]) -> Option<u8> {
    let mut unique = ranks.to_vec();
    unique.sort_unstable();
    unique.dedup();
    if unique.len() != 5 {
        return None;
    }
    if unique == [2, 3, 4, 5, 14] {
        return Some(5);
    }
    if unique[4] - unique[0] == 4 {
        return Some(unique[4]);
    }
    None
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Action {
    Fold,
    Check,
    Call,
    Bet,
    Raise,
    AllIn,
}

impl Action {
    pub fn parse(text: &str) -> Result<Self, String> {
        match text {
            "fold" => Ok(Self::Fold),
            "check" => Ok(Self::Check),
            "call" => Ok(Self::Call),
            "bet" => Ok(Self::Bet),
            "raise" => Ok(Self::Raise),
            "all-in" => Ok(Self::AllIn),
            _ => Err(format!("unknown Hold'em action: {text}")),
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Fold => "fold",
            Self::Check => "check",
            Self::Call => "call",
            Self::Bet => "bet",
            Self::Raise => "raise",
            Self::AllIn => "all-in",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Street {
    Preflop,
    Flop,
    Turn,
    River,
    Showdown,
}

impl Street {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Preflop => "preflop",
            Self::Flop => "flop",
            Self::Turn => "turn",
            Self::River => "river",
            Self::Showdown => "showdown",
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct HoldemState {
    pub deck_cards: Vec<Card>,
    pub hole_cards: [[Card; 2]; 2],
    pub board: Vec<Card>,
    pub street: Street,
    pub button: usize,
    pub current_player: usize,
    pub stacks: [i32; 2],
    pub contributions: [i32; 2],
    pub street_bets: [i32; 2],
    pub acted: [bool; 2],
    pub raises_this_street: u8,
    pub terminal: bool,
    pub folded_player: Option<usize>,
    pub history: Vec<String>,
}

impl HoldemState {
    pub fn new(deck_cards: Vec<Card>, hole_cards: [[Card; 2]; 2]) -> Self {
        Self::new_with_options(deck_cards, hole_cards, STARTING_STACK, 0)
    }

    pub fn new_with_options(
        deck_cards: Vec<Card>,
        hole_cards: [[Card; 2]; 2],
        starting_stack: i32,
        button: usize,
    ) -> Self {
        let small_blind_player = button;
        let big_blind_player = 1 - button;
        let mut stacks = [starting_stack, starting_stack];
        let mut contributions = [0, 0];
        let mut street_bets = [0, 0];
        for (player, blind) in [(small_blind_player, SMALL_BLIND), (big_blind_player, BIG_BLIND)] {
            let posted = stacks[player].min(blind);
            stacks[player] -= posted;
            contributions[player] += posted;
            street_bets[player] += posted;
        }
        Self {
            deck_cards,
            hole_cards,
            board: Vec::new(),
            street: Street::Preflop,
            button,
            current_player: small_blind_player,
            stacks,
            contributions,
            street_bets,
            acted: [false, false],
            raises_this_street: 0,
            terminal: false,
            folded_player: None,
            history: Vec::new(),
        }
    }

    pub fn from_seed(seed: u64) -> Self {
        Self::from_seed_with_options(seed, STARTING_STACK, 0)
    }

    pub fn from_seed_with_options(seed: u64, starting_stack: i32, button: usize) -> Self {
        let cards = shuffled_deck(seed);
        let small_blind_player = button;
        let big_blind_player = 1 - button;
        let mut hole_cards = [[cards[0], cards[0]], [cards[0], cards[0]]];
        hole_cards[small_blind_player] = [cards[0], cards[2]];
        hole_cards[big_blind_player] = [cards[1], cards[3]];
        Self::new_with_options(cards[4..].to_vec(), hole_cards, starting_stack, button)
    }

    pub fn small_blind_player(&self) -> usize {
        self.button
    }

    pub fn big_blind_player(&self) -> usize {
        1 - self.button
    }

    pub fn pot(&self) -> i32 {
        self.contributions[0] + self.contributions[1]
    }

    pub fn to_call(&self, player: usize) -> i32 {
        self.street_bets[0].max(self.street_bets[1]) - self.street_bets[player]
    }

    pub fn bet_size(&self) -> i32 {
        if matches!(self.street, Street::Preflop | Street::Flop) {
            BIG_BLIND
        } else {
            BIG_BLIND * 2
        }
    }

    pub fn legal_actions(&self) -> Vec<Action> {
        if self.terminal || self.stacks[self.current_player] <= 0 {
            return Vec::new();
        }
        let to_call = self.to_call(self.current_player);
        let stack = self.stacks[self.current_player];
        if to_call > 0 {
            let mut actions = vec![Action::Fold, Action::Call];
            if self.raises_this_street < MAX_RAISES_PER_STREET
                && stack > to_call
                && stack >= to_call + self.bet_size()
            {
                actions.push(Action::Raise);
            }
            actions.push(Action::AllIn);
            return actions;
        }
        let mut actions = vec![Action::Check];
        if self.raises_this_street < MAX_RAISES_PER_STREET && stack >= self.bet_size() {
            actions.push(Action::Bet);
        }
        actions.push(Action::AllIn);
        actions
    }

    pub fn apply(&self, action: Action) -> Result<Self, String> {
        if !self.legal_actions().contains(&action) {
            return Err(format!(
                "illegal action {}; legal={}",
                action.as_str(),
                self.legal_action_text()
            ));
        }
        let mut next = self.clone();
        match action {
            Action::Fold => {
                next.terminal = true;
                next.folded_player = Some(self.current_player);
                next.push_history(action, 0);
                return Ok(next);
            }
            Action::Check => {
                next.acted[self.current_player] = true;
                next.push_history(action, 0);
            }
            Action::Call => {
                let amount = self.to_call(self.current_player);
                next.commit(amount, action);
            }
            Action::Bet | Action::Raise => {
                let amount = self.to_call(self.current_player) + self.bet_size();
                next.commit(amount, action);
            }
            Action::AllIn => {
                next.commit(self.stacks[self.current_player], action);
            }
        }

        if next.street_closed() {
            next.advance_after_closed_betting();
        } else {
            next.current_player = 1 - self.current_player;
        }
        Ok(next)
    }

    pub fn showdown_winner(&self) -> Result<Option<usize>, String> {
        if self.board.len() != 5 {
            return Err("showdown winner requires a complete board".to_string());
        }
        let mut p0 = Vec::with_capacity(7);
        let mut p1 = Vec::with_capacity(7);
        p0.extend(self.hole_cards[0]);
        p1.extend(self.hole_cards[1]);
        p0.extend(self.board.iter().copied());
        p1.extend(self.board.iter().copied());
        let s0 = evaluate_hand(&p0)?;
        let s1 = evaluate_hand(&p1)?;
        if s0 == s1 {
            Ok(None)
        } else if s0 > s1 {
            Ok(Some(0))
        } else {
            Ok(Some(1))
        }
    }

    pub fn final_stacks(&self) -> Result<[i32; 2], String> {
        if !self.terminal {
            return Err("final stacks are only defined for terminal states".to_string());
        }
        let mut stacks = self.stacks;
        if let Some(folded) = self.folded_player {
            stacks[1 - folded] += self.pot();
            return Ok(stacks);
        }
        match self.showdown_winner()? {
            Some(winner) => stacks[winner] += self.pot(),
            None => {
                stacks[0] += self.pot() / 2 + self.pot() % 2;
                stacks[1] += self.pot() / 2;
            }
        }
        Ok(stacks)
    }

    pub fn utility(&self, player: usize) -> Result<i32, String> {
        let starting_stack = self.stacks[player] + self.contributions[player];
        Ok(self.final_stacks()?[player] - starting_stack)
    }

    pub fn trace_summary(&self) -> String {
        format!(
            "street={};current={};board={};stacks={:?};contributions={:?};terminal={};history={};legal={};u0={}",
            self.street.as_str(),
            self.current_player,
            card_list(&self.board),
            self.stacks,
            self.contributions,
            self.terminal,
            self.history.join(","),
            self.legal_action_text(),
            if self.terminal { self.utility(0).unwrap_or(0) } else { 0 },
        )
    }

    fn commit(&mut self, amount: i32, action: Action) {
        let player = self.current_player;
        let amount = amount.min(self.stacks[player]);
        let old_max_bet = self.street_bets[0].max(self.street_bets[1]);
        self.stacks[player] -= amount;
        self.contributions[player] += amount;
        self.street_bets[player] += amount;
        let new_bet = self.street_bets[player];
        let is_aggressive = matches!(action, Action::Bet | Action::Raise | Action::AllIn) && new_bet > old_max_bet;
        let is_full_raise = is_aggressive && (new_bet - old_max_bet) >= self.bet_size();
        if is_aggressive {
            self.acted = [false, false];
        }
        self.acted[player] = true;
        if is_full_raise {
            self.raises_this_street += 1;
        }
        self.push_history(action, amount);
    }

    fn street_closed(&self) -> bool {
        if !self.acted[0] || !self.acted[1] {
            return false;
        }
        self.street_bets[0] == self.street_bets[1] || self.stacks[0] == 0 || self.stacks[1] == 0
    }

    fn advance_after_closed_betting(&mut self) {
        if self.stacks[0] == 0 || self.stacks[1] == 0 {
            self.runout_to_showdown();
        } else if self.street == Street::River {
            self.terminal = true;
            self.street = Street::Showdown;
        } else {
            self.advance_street();
        }
    }

    fn advance_street(&mut self) {
        match self.street {
            Street::Preflop => {
                self.board.extend(self.deck_cards.drain(..3));
                self.street = Street::Flop;
            }
            Street::Flop => {
                self.board.push(self.deck_cards.remove(0));
                self.street = Street::Turn;
            }
            Street::Turn => {
                self.board.push(self.deck_cards.remove(0));
                self.street = Street::River;
            }
            Street::River | Street::Showdown => {
                self.terminal = true;
                self.street = Street::Showdown;
            }
        }
        self.current_player = self.big_blind_player();
        self.street_bets = [0, 0];
        self.acted = [false, false];
        self.raises_this_street = 0;
    }

    fn runout_to_showdown(&mut self) {
        let needed = 5 - self.board.len();
        self.board.extend(self.deck_cards.drain(..needed));
        self.street = Street::Showdown;
        self.terminal = true;
    }

    fn push_history(&mut self, action: Action, amount: i32) {
        self.history.push(format!(
            "{}:p{}:{}:{}",
            self.street.as_str(),
            self.current_player,
            action.as_str(),
            amount
        ));
    }

    fn legal_action_text(&self) -> String {
        self.legal_actions()
            .iter()
            .map(|action| action.as_str())
            .collect::<Vec<_>>()
            .join(",")
    }
}

pub fn card_list(cards: &[Card]) -> String {
    cards
        .iter()
        .map(|card| card.to_string())
        .collect::<Vec<_>>()
        .join(" ")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn c(text: &str) -> Card {
        Card::parse(text).unwrap()
    }

    #[test]
    fn deck_has_52_unique_cards() {
        let cards = deck();
        let mut unique = cards.iter().map(|card| card.to_string()).collect::<Vec<_>>();
        unique.sort();
        unique.dedup();
        assert_eq!(cards.len(), 52);
        assert_eq!(unique.len(), 52);
    }

    #[test]
    fn seeded_deals_and_button_one_blinds_are_deterministic() {
        let first = HoldemState::from_seed_with_options(17, 100, 1);
        let second = HoldemState::from_seed_with_options(17, 100, 1);
        let other = HoldemState::from_seed_with_options(18, 100, 1);

        assert_eq!(first.hole_cards, second.hole_cards);
        assert_eq!(first.deck_cards, second.deck_cards);
        assert_ne!((first.hole_cards, first.deck_cards.clone()), (other.hole_cards, other.deck_cards));
        assert_eq!(first.button, 1);
        assert_eq!(first.small_blind_player(), 1);
        assert_eq!(first.big_blind_player(), 0);
        assert_eq!(first.current_player, 1);
        assert_eq!(first.stacks, [98, 99]);
        assert_eq!(first.contributions, [2, 1]);
    }

    #[test]
    fn evaluator_orders_categories_and_wheel() {
        let high = evaluate_hand(&[c("As"), c("Kd"), c("9h"), c("7c"), c("3s")]).unwrap();
        let pair = evaluate_hand(&[c("As"), c("Ad"), c("9h"), c("7c"), c("3s")]).unwrap();
        let flush = evaluate_hand(&[c("As"), c("Ks"), c("9s"), c("7s"), c("3s")]).unwrap();
        let quads = evaluate_hand(&[c("As"), c("Ad"), c("Ah"), c("Ac"), c("3s")]).unwrap();
        let wheel = evaluate_hand(&[c("As"), c("2d"), c("3h"), c("4c"), c("5s")]).unwrap();
        assert!(high < pair);
        assert!(pair < flush);
        assert!(flush < quads);
        assert_eq!(wheel, [4, 5, 0, 0, 0, 0]);
    }

    #[test]
    fn call_check_advances_to_flop_with_big_blind_first() {
        let state = HoldemState::new(
            vec![c("2c"), c("3c"), c("4c"), c("5d"), c("6d")],
            [[c("As"), c("Kd")], [c("Qh"), c("Jh")]],
        )
        .apply(Action::Call)
        .unwrap()
        .apply(Action::Check)
        .unwrap();

        assert_eq!(state.street, Street::Flop);
        assert_eq!(state.current_player, 1);
        assert_eq!(card_list(&state.board), "2c 3c 4c");
    }

    #[test]
    fn all_in_call_runs_out_to_showdown() {
        let mut state = HoldemState::new(
            vec![c("2c"), c("7d"), c("9s"), c("Tc"), c("3h")],
            [[c("As"), c("Ad")], [c("Qh"), c("Jh")]],
        );
        state.stacks = [3, 98];
        state.contributions = [1, 2];
        state.street_bets = [1, 2];
        let state = state
            .apply(Action::AllIn)
            .unwrap()
            .apply(Action::Call)
            .unwrap();

        assert!(state.terminal);
        assert_eq!(state.street, Street::Showdown);
        assert_eq!(state.showdown_winner().unwrap(), Some(0));
        assert_eq!(state.final_stacks().unwrap(), [8, 96]);
        assert_eq!(state.utility(0).unwrap(), 4);
    }
}
