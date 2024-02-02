from . import game, cards, seats
import argparse
from random import Random
from functools import partial
import os


Table = dict[int, seats.Seat]


def serialize_card(card: cards.Card) -> str:
    return card.suit + card.rank


def serialize_hand(hand: cards.Hand) -> str:
    return " ".join(map(serialize_card, sorted(hand, key=cards.make_card_key())))


def unserialize_card(data: str) -> cards.Card | None:
    if data:
        return cards.Card(suit=data[0], rank=data[1:])
    else:
        return None


def broadcast(table: Table, message: str) -> None:
    for player in table:
        table[player].send(message)


def make_bid(table: Table, bidder: int) -> int:
    table[bidder].send("bid ?")
    request = table[bidder].receive()

    try:
        return int(request)
    except ValueError:
        return 0


def send_bid(table: Table, bidder: int, bid: int) -> None:
    broadcast(table, f"bid {bidder} {bid}")


def play_card(table: Table, player: int, playable: cards.Hand) -> cards.Card:
    #print(f"<DEBUG> player {player} plays - " f"playable={serialize_hand(playable)}")

    table[player].send("card ?")
    request = table[player].receive()
    card = unserialize_card(request)

    if card not in playable:
        #print(f"<DEBUG> invalid card '{request}'")
        card = sorted(playable, key=cards.make_card_key())[0]

    broadcast(table, f"card {player} {serialize_card(card)}")
    #print(f"<DEBUG> played {serialize_card(card)}")

    return card


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="judge")
    parser.add_argument("-s", "--seed", type=int, default=-1)
    parser.add_argument("-r", "--rounds", type=int, default=10)
    parser.add_argument("--program", nargs="+", action="append")

    args = parser.parse_args()

    if args.seed == -1:
        args.seed = int.from_bytes(os.urandom(8), byteorder="big")

    if args.program is None:
        args.program = [["terminal"]]

    return args


def setup_table(programs: list[list[str]]) -> Table:
    table: Table = {}

    for player in range(4):
        program = programs[player % len(programs)]

        # RANDOM BOT
        if player == 0:
            table[player] = seats.RandomBotSeat(player)
        
        # other players
        elif program == ["terminal"]:
            table[player] = seats.TerminalSeat(player)

        else:
            table[player] = seats.SubprocessSeat(player, program)
        
        

        table[player].send(f"player {player}")
        #print(f"<DEBUG> player {player} - seat={table[player]}")

    return table


def run() -> None:
    args = parse_args()
    table = setup_table(args.program)
    #print(f"<DEBUG> seed={args.seed}")

    random = Random(args.seed)
    total_scores = {0: 0, 1: 0}
    starter = 0

    for _ in range(args.rounds):
        hands = cards.deal_hands(random)

        for player, hand in enumerate(hands):
            table[player].send(f"hand {serialize_hand(hand)}")


            #print(f"<DEBUG> player {player} - hand={serialize_hand(hand)}")

        winner, bid = game.bid(
            starter=starter,
            make_bid=partial(make_bid, table),
            send_bid=partial(send_bid, table),
        )

        scores = game.play(
            starter=winner,
            hands=hands,
            play_card=partial(play_card, table),
        )

        print(f"{scores=}")

        bidding_team = winner % 2
        other_team = (winner + 1) % 2

        if bid == 105:
            if scores[bidding_team] < 100:
                total_scores[other_team] += 500
            else:
                total_scores[bidding_team] += 500
        else:
            if scores[bidding_team] < bid:
                total_scores[bidding_team] -= bid
            else:
                total_scores[bidding_team] += scores[bidding_team]

            total_scores[other_team] += scores[other_team]

        print(f"{total_scores=}")
        starter = (starter + 1) % 4

    broadcast(table, "end")


run()
