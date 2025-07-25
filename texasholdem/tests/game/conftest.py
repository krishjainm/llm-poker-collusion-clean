"""
Config for game tests. Includes:
    - History file with comments
    - Call player fixture
    - And a method containing assert checks for the prehand for a game
"""
import random

import pytest

from texasholdem.game.game import TexasHoldEm
from texasholdem.game.hand_phase import HandPhase
from texasholdem.game.action_type import ActionType
from texasholdem.game.player_state import PlayerState

from tests.conftest import GOOD_GAME_HISTORY_DIRECTORY


BASIC_GAME_RUNS = 100
UNTIL_STOP_RUNS = 1000


@pytest.fixture()
def history_file_with_comments():
    """
    Returns:
        str: A path to a valid history file with comments
    """
    return GOOD_GAME_HISTORY_DIRECTORY / "call_game_6.pgn"


def prehand_checks(texas: TexasHoldEm):
    # pylint: disable=too-many-branches,too-many-statements
    """
    Tests basic state after running prehand:
        - hand_phase state should be PREFLOP
        - game_state should be RUNNING
        - Blinds should be posted
        - Blind locations should be sequential
        - Players should have TO_CALL status, (big blind player should have IN status)
        - Current player should be left of Big blind
        - Players should have 2 cards
        - The Board should not have any cards

    """
    # pylint: disable=protected-access
    assert texas.hand_phase == HandPhase.PREHAND, "Expected HandPhase to be PREHAND"

    # Gather pre-info to check differences / info that will be overwritten
    player_chips = [texas.players[i].chips for i in range(texas.max_players)]
    active_players = [i for i in range(texas.max_players) if player_chips[i] > 0]

    # RUN PREHAND
    texas.start_hand()

    # state info
    sb_posted = min(texas.small_blind, player_chips[texas.sb_loc])
    bb_posted = min(texas.big_blind, player_chips[texas.bb_loc])
    game_running = len(active_players) >= 2
    hand_running = game_running and not texas._is_hand_over()

    assert (
        texas.is_game_running() == game_running
    ), "Expected game to be running iff >= 2 active players"
    assert (
        texas.is_hand_running() == hand_running
    ), "Expected hand to be running iff 2 or more players can take actions"

    if not game_running or not hand_running:
        assert (
            texas.hand_phase == HandPhase.PREHAND
        ), "If game/hand was not running, expected HandPhase to reset to PREHAND"
        return

    # check hand_phase
    assert (
        texas.hand_phase == HandPhase.PREFLOP
    ), "Ran PREHAND, expected next HandPhase to be PREFLOP"

    # check blind locations
    assert (
        0 <= texas.btn_loc < texas.max_players
    ), f"Expected the blind to be in [0, {texas.max_players})"

    if len(active_players) > 2:
        assert (
            texas.sb_loc
            == active_players[
                (active_players.index(texas.btn_loc) + 1) % len(active_players)
            ]
        ), (
            "Expected the small blind to be to left of "
            f"big blind in a {len(active_players)}-player game"
        )
    else:
        assert (
            texas.btn_loc == texas.sb_loc
        ), "Expected the button and small blind to be the same place in a 2-player game"

    assert (
        texas.bb_loc
        == active_players[
            (active_players.index(texas.sb_loc) + 1) % len(active_players)
        ]
    ), "Expected the big blind to be to the left of the small blind"
    assert (
        texas.current_player
        == active_players[
            (active_players.index(texas.bb_loc) + 1) % len(active_players)
        ]
    ), "Expected the current player to be to the left of the big blind"

    # check blind posting / blind states
    if player_chips[texas.sb_loc] <= texas.small_blind:
        assert (
            texas.players[texas.sb_loc].chips == 0
        ), "Expected the small blind to post what they have if <= the small blind"
        assert (
            texas.players[texas.sb_loc].state == PlayerState.ALL_IN
        ), "Expected the small blind to be ALL_IN after posting everything"
    else:
        assert (
            texas.players[texas.sb_loc].chips == player_chips[texas.sb_loc] - sb_posted
        ), "Expected the small blind to post exactly the small blind"

        if sb_posted < bb_posted:
            assert (
                texas.players[texas.sb_loc].state == PlayerState.TO_CALL
            ), "Expected the small blind to have state TO_CALL"
        else:
            assert (
                texas.players[texas.sb_loc].state == PlayerState.IN
            ), "Expected the small blind who posted more than the big blind to have state IN"

    if player_chips[texas.bb_loc] <= texas.big_blind:
        assert (
            texas.players[texas.bb_loc].chips == 0
        ), "Expected the big blind to post what they have if <= the big blind"
        assert (
            texas.players[texas.bb_loc].state == PlayerState.ALL_IN
        ), "Expected the big blind to be ALL_IN after posting everything"
    else:
        assert (
            texas.players[texas.bb_loc].chips == player_chips[texas.bb_loc] - bb_posted
        ), "Expected the big blind to post exactly the big blind"
        assert (
            texas.players[texas.bb_loc].state == PlayerState.IN
        ), "Expected the big blind to have state IN"

    for i in active_players:
        if i not in (texas.sb_loc, texas.bb_loc):
            assert (
                texas.players[i].chips == player_chips[i]
            ), f"Expected player {i} to not have posted anything"

    assert (
        sum(pot.get_total_amount() for pot in texas.pots) == sb_posted + bb_posted
    ), "Expected pot to be the sum of sb posted and bb posted"

    # check player states
    # players have TO_CALL, (we check the small blind above)
    assert all(
        texas.players[i].state == PlayerState.TO_CALL
        for i in active_players
        if i not in (texas.sb_loc, texas.bb_loc)
    ), "Expected all players to need to call in the pot"

    # if 0 chips skip
    for player_id, chips in enumerate(player_chips, 0):
        if chips == 0:
            assert (
                texas.players[player_id].state == PlayerState.SKIP
            ), f"Expected player {player_id} with 0 chips to have status SKIP"

    # check chips to call
    for i in active_players:
        if i not in (texas.sb_loc, texas.bb_loc):
            chips_to_call = sum(
                texas.pots[pot_id].raised - texas.pots[pot_id].get_player_amount(i)
                for pot_id in range(texas.players[i].last_pot + 1)
            )
            assert texas.chips_to_call(i) == chips_to_call, (
                "Expected chips to call to be the raised "
                "level of the last eligible pot - player amount"
            )

    if texas.players[texas.sb_loc].state != PlayerState.ALL_IN:
        assert texas.chips_to_call(texas.sb_loc) == max(
            0, bb_posted - sb_posted
        ), "Expected small blind to have to call big_blind - small_blind number of chips"
    assert (
        texas.chips_to_call(texas.bb_loc) == 0
    ), "Expected big blind to have to call 0 chips"

    # players have cards
    assert all(
        len(texas.get_hand(i)) == 2 for i in active_players
    ), "Expected all active players to have 2 cards."

    # board does not have cards
    assert not texas.board, "Expected the board to be empty"


class GamePredicate:
    """
    Predicate to run for the automated fuzz checker that runs
    a complete tournament. The before method will run before every action
    and the after method will run after every action.

    They will return True if there is an error.

    """

    settle: bool = False
    """
    If this predicate should run in the SETTLE phase.
    """

    def before(self, game: TexasHoldEm) -> bool:
        # pylint: disable=unused-argument
        """
        This method will run before every action. Predicates can use this
        to set variables they will check in the after method or to validate moves.

        Returns:
            bool: True if there was an error, false o/w

        """
        return False

    def after(self, game: TexasHoldEm) -> bool:
        # pylint: disable=unused-argument
        """
        This method will run after every action.

        Returns:
            bool: True if there was an error, false o/w

        """
        return False


class EmptyPots(GamePredicate):
    """
    Checks if any pot has a total amount of 0.
    """

    def after(self, game: TexasHoldEm) -> bool:
        return any(pot.get_total_amount() == 0 for pot in game.pots)


class LastRaiseChecker(GamePredicate):
    """
    Checks if the last raise attribute is correct.
    """

    before_last_raise = None

    def before(self, game: TexasHoldEm):
        self.before_last_raise = game.last_raise

    def after(self, game: TexasHoldEm) -> bool:
        actions = game.hand_history[game.hand_phase].actions
        if not actions:
            return False

        value = actions[-1].value or 0
        return game.last_raise == (game.last_raise - value)


class MinRaiseChecker(GamePredicate):
    """
    Checks if the min raise method is correct.
    """

    def after(self, game: TexasHoldEm) -> bool:
        return game.min_raise() == max(game.big_blind, game.last_raise)


class RaiseOptionChecker(GamePredicate):
    """
    Checks that if the raise option is unset, then raise should be invalid
    """

    def before(self, game: TexasHoldEm) -> bool:
        return not game.raise_option and game.validate_move(
            action=ActionType.RAISE,
            total=game.value_to_total(game.min_raise(), game.current_player),
        )


class AvailableMoveChecker(GamePredicate):
    """
    Checks that the get_available_moves() function is all valid
    """

    def before(self, game: TexasHoldEm) -> bool:
        # pylint: disable=too-many-return-statements,too-many-branches
        moves = game.get_available_moves()

        for action, total in moves.sample(num=5):
            game.validate_move(action=action, total=total)

        bet_amount = game.player_bet_amount(game.current_player)
        chips = game.players[game.current_player].chips
        min_raise = game.value_to_total(game.min_raise(), game.current_player)
        max_raise = bet_amount + chips

        if (
            game.players[game.current_player].state == PlayerState.IN
            and ActionType.CALL in moves
        ):
            return True
        if (
            game.players[game.current_player].state == PlayerState.TO_CALL
            and ActionType.CHECK in moves
        ):
            return True

        if not game.raise_option:
            if ActionType.RAISE in moves:
                return True
        elif max_raise < min_raise:
            if game.chips_to_call(game.current_player) < chips:
                if (ActionType.RAISE, max_raise) not in moves:
                    return True
            else:
                if ActionType.RAISE in moves:
                    return True
        elif ActionType.RAISE in moves:
            if (ActionType.RAISE, min_raise) not in moves:
                return True
            if (ActionType.RAISE, min_raise - 1) in moves:
                return True
            if (ActionType.RAISE, max_raise) not in moves:
                return True
            if (ActionType.RAISE, max_raise + 1) in moves:
                return True

        return False


class CopyChecker(GamePredicate):
    """
    Checks that if the raise option is unset, then raise should be invalid
    """

    game_copy = None
    shuffle = True

    def before(self, game: TexasHoldEm) -> bool:
        self.shuffle = random.randint(0, 1) == 1
        self.game_copy = game.copy(shuffle=self.shuffle)

    def after(self, game: TexasHoldEm) -> bool:
        last_action = game.hand_history.combined_actions()[-1]
        self.game_copy.take_action(last_action.action_type, total=last_action.total)

        return self.game_copy.hand_history.to_string() != game.hand_history.to_string()


GAME_PREDICATES = (
    EmptyPots(),
    LastRaiseChecker(),
    MinRaiseChecker(),
    RaiseOptionChecker(),
    AvailableMoveChecker(),
    CopyChecker(),
)
