use std::fmt;

pub const ANTE: i32 = 1;
pub const BET_SIZES: [i32; 2] = [2, 4];
pub const MAX_RAISES: u8 = 2;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Rank {
    J,
    Q,
    K,
}

impl Rank {
    pub fn value(self) -> u8 {
        match self {
            Rank::J => 0,
            Rank::Q => 1,
            Rank::K => 2,
        }
    }
}

impl fmt::Display for Rank {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let label = match self {
            Rank::J => "J",
            Rank::Q => "Q",
            Rank::K => "K",
        };
        write!(f, "{label}")
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Card {
    pub rank: Rank,
    pub copy: u8,
}

impl Card {
    pub const fn new(rank: Rank, copy: u8) -> Self {
        Self { rank, copy }
    }
}

pub const CARDS: [Card; 6] = [
    Card::new(Rank::J, 1),
    Card::new(Rank::J, 2),
    Card::new(Rank::Q, 1),
    Card::new(Rank::Q, 2),
    Card::new(Rank::K, 1),
    Card::new(Rank::K, 2),
];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Action {
    Check,
    Bet,
    Call,
    Raise,
    Fold,
}

impl Action {
    pub fn token(self) -> char {
        match self {
            Action::Check => 'k',
            Action::Bet => 'b',
            Action::Call => 'c',
            Action::Raise => 'r',
            Action::Fold => 'f',
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct LeducState {
    pub deal: [Card; 3],
    pub round_index: usize,
    pub current_player: usize,
    pub contributions: [i32; 2],
    pub round_bets: [i32; 2],
    pub raises_this_round: u8,
    pub history: [Vec<Action>; 2],
    pub terminal: bool,
    pub folded_player: Option<usize>,
}

impl LeducState {
    pub fn new(deal: [Card; 3]) -> Result<Self, String> {
        validate_deal(&deal)?;
        Ok(Self {
            deal,
            round_index: 0,
            current_player: 0,
            contributions: [ANTE, ANTE],
            round_bets: [0, 0],
            raises_this_round: 0,
            history: [Vec::new(), Vec::new()],
            terminal: false,
            folded_player: None,
        })
    }

    pub fn pot(&self) -> i32 {
        self.contributions[0] + self.contributions[1]
    }

    pub fn private_cards(&self) -> [Card; 2] {
        [self.deal[0], self.deal[1]]
    }

    pub fn public_card(&self) -> Card {
        self.deal[2]
    }

    pub fn to_call(&self, player: usize) -> i32 {
        self.round_bets[0].max(self.round_bets[1]) - self.round_bets[player]
    }

    pub fn legal_actions(&self) -> Vec<Action> {
        if self.terminal {
            return Vec::new();
        }

        if self.to_call(self.current_player) > 0 {
            let mut actions = vec![Action::Fold, Action::Call];
            if self.raises_this_round < MAX_RAISES {
                actions.push(Action::Raise);
            }
            return actions;
        }

        let mut actions = vec![Action::Check];
        if self.raises_this_round < MAX_RAISES {
            actions.push(Action::Bet);
        }
        actions
    }

    pub fn apply(&self, action: Action) -> Result<Self, String> {
        if !self.legal_actions().contains(&action) {
            return Err(format!("illegal action {:?}; legal={:?}", action, self.legal_actions()));
        }

        let mut next = self.clone();
        next.history[self.round_index].push(action);

        match action {
            Action::Fold => {
                next.terminal = true;
                next.folded_player = Some(self.current_player);
            }
            Action::Call => {
                let call = self.to_call(self.current_player);
                next.contributions[self.current_player] += call;
                next.round_bets[self.current_player] += call;
                next = next.after_closed_betting();
            }
            Action::Bet | Action::Raise => {
                let amount = self.to_call(self.current_player) + BET_SIZES[self.round_index];
                next.contributions[self.current_player] += amount;
                next.round_bets[self.current_player] += amount;
                next.raises_this_round += 1;
                next.current_player = 1 - self.current_player;
            }
            Action::Check => {
                let round_history = &next.history[self.round_index];
                if round_history.len() >= 2
                    && round_history[round_history.len() - 2] == Action::Check
                    && round_history[round_history.len() - 1] == Action::Check
                {
                    next = next.after_closed_betting();
                } else {
                    next.current_player = 1 - self.current_player;
                }
            }
        }
        Ok(next)
    }

    fn after_closed_betting(mut self) -> Self {
        if self.round_index == 0 {
            self.round_index = 1;
            self.current_player = 0;
            self.round_bets = [0, 0];
            self.raises_this_round = 0;
        } else {
            self.terminal = true;
        }
        self
    }

    pub fn utility(&self, player: usize) -> Result<f64, String> {
        if !self.terminal {
            return Err("utility is only defined for terminal states".to_string());
        }

        let winner = match self.folded_player {
            Some(folded) => Some(1 - folded),
            None => self.showdown_winner(),
        };

        Ok(match winner {
            None => self.pot() as f64 / 2.0 - self.contributions[player] as f64,
            Some(winner) if winner == player => (self.pot() - self.contributions[player]) as f64,
            Some(_) => -(self.contributions[player] as f64),
        })
    }

    pub fn showdown_winner(&self) -> Option<usize> {
        let [p0, p1] = self.private_cards();
        let public = self.public_card().rank;
        let pair0 = p0.rank == public;
        let pair1 = p1.rank == public;
        if pair0 != pair1 {
            return Some(if pair0 { 0 } else { 1 });
        }
        if p0.rank.value() == p1.rank.value() {
            return None;
        }
        Some(if p0.rank.value() > p1.rank.value() { 0 } else { 1 })
    }

    pub fn info_set_key(&self, player: usize) -> String {
        let private = self.private_cards()[player].rank;
        let public = if self.round_index == 1 {
            self.public_card().rank.to_string()
        } else {
            "-".to_string()
        };
        let h0 = history_string(&self.history[0]);
        let h1 = history_string(&self.history[1]);
        format!("p{player}|{private}|{public}|r{}|{h0}/{h1}", self.round_index)
    }
}

pub fn deal_from_indices(indices: [usize; 3]) -> Result<[Card; 3], String> {
    if indices.iter().any(|idx| *idx >= CARDS.len()) {
        return Err("card index out of range".to_string());
    }
    let deal = [CARDS[indices[0]], CARDS[indices[1]], CARDS[indices[2]]];
    validate_deal(&deal)?;
    Ok(deal)
}

fn history_string(history: &[Action]) -> String {
    if history.is_empty() {
        "-".to_string()
    } else {
        history.iter().map(|action| action.token()).collect()
    }
}

fn validate_deal(deal: &[Card; 3]) -> Result<(), String> {
    for i in 0..deal.len() {
        for j in (i + 1)..deal.len() {
            if deal[i] == deal[j] {
                return Err("deal must contain three unique cards".to_string());
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn state(indices: [usize; 3]) -> LeducState {
        LeducState::new(deal_from_indices(indices).unwrap()).unwrap()
    }

    fn play_to_showdown(indices: [usize; 3]) -> LeducState {
        state(indices)
            .apply(Action::Check)
            .unwrap()
            .apply(Action::Check)
            .unwrap()
            .apply(Action::Check)
            .unwrap()
            .apply(Action::Check)
            .unwrap()
    }

    #[test]
    fn initial_legal_actions() {
        let s = state([4, 2, 0]);
        assert_eq!(s.legal_actions(), vec![Action::Check, Action::Bet]);
        assert_eq!(s.pot(), 2);
        assert_eq!(s.contributions, [1, 1]);
    }

    #[test]
    fn check_check_advances_round() {
        let s = state([4, 2, 0])
            .apply(Action::Check)
            .unwrap()
            .apply(Action::Check)
            .unwrap();
        assert_eq!(s.round_index, 1);
        assert_eq!(s.current_player, 0);
        assert_eq!(s.round_bets, [0, 0]);
        assert!(!s.terminal);
    }

    #[test]
    fn bet_call_advances_round() {
        let s = state([4, 2, 0])
            .apply(Action::Bet)
            .unwrap()
            .apply(Action::Call)
            .unwrap();
        assert_eq!(s.round_index, 1);
        assert_eq!(s.current_player, 0);
        assert_eq!(s.contributions, [3, 3]);
        assert_eq!(s.pot(), 6);
        assert_eq!(s.round_bets, [0, 0]);
    }

    #[test]
    fn bet_fold_terminal() {
        let s = state([4, 2, 0])
            .apply(Action::Bet)
            .unwrap()
            .apply(Action::Fold)
            .unwrap();
        assert!(s.terminal);
        assert_eq!(s.folded_player, Some(1));
        assert_eq!(s.legal_actions(), Vec::<Action>::new());
        assert_eq!(s.utility(0).unwrap(), 1.0);
        assert_eq!(s.utility(1).unwrap(), -1.0);
    }

    #[test]
    fn showdown_pair_beats_high_card() {
        let s = play_to_showdown([4, 2, 3]);
        assert_eq!(s.showdown_winner(), Some(1));
        assert_eq!(s.utility(1).unwrap(), 1.0);
    }

    #[test]
    fn info_set_key_hides_opponent_card() {
        let king_vs_queen = state([4, 2, 0]);
        let king_vs_jack = state([4, 0, 1]);
        assert_eq!(king_vs_queen.info_set_key(0), king_vs_jack.info_set_key(0));
        assert!(!king_vs_queen.info_set_key(0).contains('Q'));
    }
}

