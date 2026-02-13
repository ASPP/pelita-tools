import sys
import os
from pathlib import Path
import numpy as np
import subprocess
import base64
import pickle


# Config
NUM_GAMES_PER_CONSTELLATION = 10
MAX_ROUNDS_PER_GAME = 50
BOT_DIRECTORY = "./sparring_bots/" # we use all bots that fit `{BOT_DIRECTORY}/*/{BOT_FILE_NAME}`
BOT_FILE_NAME = 'bot_comp.py'
ENEMY_BOT_PATH = "./bots/demo01_stopping.py"
BENCHMARK_SCRIPT = './test_timeouts_benchmark.py'
SAVE_STATS_DICT = True
SAVE_STATS_DICT_PATH = "./stats.pickle"
FORMAT_PRINTED_DECIMALS = '10.7f'


# get path to all bots to be benchmarked
def get_paths_of_all_bots_from_subdirs(bot_directory_path=BOT_DIRECTORY, bot_file_name=BOT_FILE_NAME):
    bots = list()
    bot_dir = Path(bot_directory_path)
    for file in os.listdir(bot_dir):
        path = bot_dir / file
        if path.is_dir():
            for module in os.listdir(path):
                if module == bot_file_name:
                    bots.append(str(path/module))
    return bots

def save_stats(data:tuple[dict,dict], path=SAVE_STATS_DICT_PATH):
    with open(path, "wb") as file:
        pickle.dump(data, file)

def load_stats(path=SAVE_STATS_DICT_PATH) -> tuple[dict,dict]:
    with open(path, "rb") as file:
        (stats_per_bot, errors_per_bot) = pickle.load(file)
    return stats_per_bot, errors_per_bot

def print_aligned_bot_name(bot_name, nth_bot, len_bots):
    #for bot_name="mybot", nth_bot=1, len_bots=10
    #with `format_str="[{:2}/{}] {}"` and `bots_len_digits=2` 
    #prints `[ 1/10] mybot`
    bots_len_digits = len(str(len_bots))
    format_str = "[{:"+ f"{bots_len_digits}" +"d}/{}] {}"
    s = format_str.format(nth_bot+1, len_bots, bot_name)
    print(s)

def print_bot_stats(bot_stats: dict, bot_errors: int, prefix=""):
    round_time_median = format(bot_stats["round_time_median"],FORMAT_PRINTED_DECIMALS)
    round_time_max = format(bot_stats["round_time_max"],FORMAT_PRINTED_DECIMALS)

    run_time_median = format(bot_stats["run_time_median"],FORMAT_PRINTED_DECIMALS)
    run_time_max = format(bot_stats["run_time_max"],FORMAT_PRINTED_DECIMALS)

    s = f"errors: {bot_errors} round median: {round_time_median} round max: {round_time_max}, run median: {run_time_median} run max: {run_time_max}"

    if len(prefix) > 0:
        prefix = prefix + " "
    print(prefix + s)
            
def desearialize_output(out:bytes) -> tuple[dict,dict]:
    """
    desearialize stdout of `BENCHMARK_SCRIPT`(`test_timeouts_benchmark.py`)
    from benchmarking a single bot. 

    `BENCHMARK_SCRIPT` can print random stuff to stdout but ends with
    `\n[base64 encoded pickle.dumps tuplle of two dicts]\n` without brackets
    """
    # print appends a "\n" at the end so we want the line before that
    # ignoring everything printed before
    searialized_bot_stats = out.split("\n".encode())[-2]

    (bot_stats, bot_errors) = pickle.loads(base64.b64decode(searialized_bot_stats))

    assert type(bot_errors) is int
    assert bot_errors >= 0
    assert type(bot_stats) is dict

    return bot_stats, bot_errors

def benchmark(bots: list[str]) -> tuple[dict, dict]:
    """
    Benchmark all bots from list `bots` which contains paths to the bots
    python files.
    """
    stats_per_bot = dict()
    all_round_times = list()
    errors_per_bot = dict()

    for nth_bot, bot_path in enumerate(bots):
        print_aligned_bot_name(bot_path, nth_bot, len(bots))

        try:
            out = subprocess.check_output([sys.executable,
                                        BENCHMARK_SCRIPT,
                                        bot_path, ENEMY_BOT_PATH,
                                        str(MAX_ROUNDS_PER_GAME), 
                                        str(NUM_GAMES_PER_CONSTELLATION)
                                        ])
            

            (bot_stats, bot_errors) = desearialize_output(out)
            
        except Exception as e:
            # catch Exception to continue benchmarking the other bots.
            sys.stderr.write("\nError running\n"+str(e)+"\n\n")
            errors_per_bot[bot_path] = NUM_GAMES_PER_CONSTELLATION # 
            continue
        
        if bot_errors == NUM_GAMES_PER_CONSTELLATION:
            errors_per_bot[bot_path] = NUM_GAMES_PER_CONSTELLATION
            continue

        errors_per_bot[bot_path] = bot_errors
        stats_per_bot[bot_path] = bot_stats

        print_bot_stats(stats_per_bot[bot_path], errors_per_bot[bot_path])
        
        all_round_times.append(stats_per_bot[bot_path]["round_times"])

    return stats_per_bot, errors_per_bot

def print_stats_per_bot_table(stats_per_bot: dict, errors_per_bot: dict):
    max_bot_path_len = max(map(len, errors_per_bot)) # errors_per_bot contains all bots, stats_per_bot doesn't have to
    aligned_bot_path_format_str = "{:" + str(max_bot_path_len) + "s}"

    for bot_path in stats_per_bot:
        prefix = aligned_bot_path_format_str.format(bot_path)
        print_bot_stats(stats_per_bot[bot_path], errors_per_bot[bot_path], prefix=prefix)
    
    errors = sum([errors_per_bot[bot_path] for bot_path in errors_per_bot])
    if errors > 0:
        print("Errors per bot:")
        unsuccessful_bots = 0

        for bot_path in errors_per_bot:
            if errors_per_bot[bot_path] > 0:
                prefix = aligned_bot_path_format_str.format(bot_path)
                print(prefix, errors_per_bot[bot_path])
                
                if errors_per_bot[bot_path] == NUM_GAMES_PER_CONSTELLATION:
                    unsuccessful_bots += 1
                
                

        print(f"\nGot {len(errors_per_bot)} bots with errors.")
        print(f"\nGot {unsuccessful_bots} bots without a successful run.")

def print_all_bots_stats(stats_per_bot: dict):
    rounds = np.concatenate([stats_per_bot[bot_stats]["round_times"] for bot_stats in stats_per_bot])
    print()
    print("Stats for rounds of all Bots:")
    print("median:", np.median(rounds))
    print("mean:", rounds.mean())
    print("std:", rounds.std())
    print("min:", rounds.min())
    print("max:", rounds.max())
    print()

    runs = np.concatenate([stats_per_bot[bot_stats]["run_times"] for bot_stats in stats_per_bot])

    print("Stats for runs of all Bots:")
    print("median:", np.median(runs))
    print("mean:", runs.mean())
    print("std:", runs.std())
    print("min:", runs.min())
    print("max:", runs.max())

bots = get_paths_of_all_bots_from_subdirs()

#bots = [bots[0]]
#bots = [bots[0], ENEMY_BOT_PATH]
#bots = [ENEMY_BOT_PATH]

stats_per_bot, errors_per_bot = benchmark(bots)

#(stats_per_bot, errors_per_bot) = load_stats()

if SAVE_STATS_DICT:
    save_stats((stats_per_bot, errors_per_bot))

print()

print_stats_per_bot_table(stats_per_bot, errors_per_bot)

print_all_bots_stats(stats_per_bot)