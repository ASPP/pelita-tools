from pelita.utils import run_background_game
import sys
from typing import Any, Callable
from time import time
from pathlib import Path
import importlib
import pickle
import base64
import os
import numpy as np


"""
call this script with arguments: `benchmarked_bot_path enemy_bot_path MAX_ROUNDS_PER_GAME NUM_GAMES_PER_CONSTELLATION` 
none of these are optional
this script prints: `[maybe something unimportant]\n[base64 encoded tuple of dicts (stats of benchmarked_bot, errors of benchmarked_bot)]\n`

data in stats with multiple seeds:
{
    int: { # seed given to pelita.run_background_game (used for layout generation and random bot moves)
        "round_times": list[float], # seconds benchmarked_bot's move function ran
        "time_median": np.float,    # median from "round_times"
        "time_max": np.float,       # max from "round_times"
        "time_sum": np.float        # sum from "round_times"
    },
    "round_times": np.array,        # concatenating of all [seed]["round_times"]
    "round_time_median": np.float,  # median of "round_times"
    "round_time_max": np.float,     # max of "round_times"
    "run_times": np.array,          # list of sum of [seed]["round_times"] for every seed
    "run_time_median": np.float,    # median of "run_times"
    "run_time_max": np.float        # max of "run_times"
}

"""

def timer_decorator(func:Callable[[Any, dict], tuple[int,int]] , storage: list):
    def wrapper(*args, **kwargs):
        start = time()
        result = func(*args, **kwargs)
        end = time()
        storage.append(end-start)
        return result
    return wrapper

def import_bot(bot_path: str):
    bot_dir = "./" + str(Path(bot_path).parent)
    sys.path.append(bot_dir)
    bot = importlib.import_module(Path(bot_path).stem)
    sys.path.remove(bot_dir)
    return bot

if __name__ == "__main__":
    # get arguments
    benchmarked_bot_path = sys.argv[1]
    enemy_bot_path = sys.argv[2]
    MAX_ROUNDS_PER_GAME = int(sys.argv[3])
    NUM_GAMES_PER_CONSTELLATION = int(sys.argv[4])

    # import bots
    benchmarked_bot = import_bot(benchmarked_bot_path)
    enemy_bot = import_bot(enemy_bot_path)

    errors = 0
    stats = dict()
    stats["name"] = benchmarked_bot.TEAM_NAME
    all_round_times = list()

    for seed in range(NUM_GAMES_PER_CONSTELLATION):
        round_times = list()
        timed_benchmarked_bot = timer_decorator(benchmarked_bot.move, round_times)

        save_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
        try:
            run_background_game(blue_move=timed_benchmarked_bot,
                                red_move=enemy_bot.move,
                                layout=None,
                                max_rounds=MAX_ROUNDS_PER_GAME,
                                seed=seed)
        except Exception as e:
            errors += 1
            sys.stderr.write(str(e))
            continue
        finally:
            sys.stdout = save_stdout
        
        
        stats[seed] = dict()
        stats[seed]["round_times"] = np.array(round_times)
        stats[seed]["time_median"] = np.median(stats[seed]["round_times"])
        stats[seed]["time_max"] = np.max(stats[seed]["round_times"])
        stats[seed]["time_sum"] = np.sum(stats[seed]["round_times"])

        all_round_times.append(stats[seed]["round_times"])

    try:
        #stats per round
        stats["round_times"] = np.concatenate(all_round_times)
        stats["round_time_median"] = np.median(stats["round_times"])
        stats["round_time_max"] = np.max([stats[seed]["time_max"] for seed in range(NUM_GAMES_PER_CONSTELLATION)])

        #stats per run
        stats["run_times"] = np.array([sum(run) for run in all_round_times])
        stats["run_time_median"] = np.median(stats["run_times"])
        stats["run_time_max"] = np.max(stats["run_times"])


    except Exception as e:
        sys.stderr.write("Error from banchmark:\n")
        sys.stderr.write(str(e)+"\n")
        stats["round_times"] = list()


    # searializing data
    pickled = (base64.b64encode(pickle.dumps((stats, errors)))).decode('utf-8')
    # sending data over stdout
    print() # send newline
    print(pickled)