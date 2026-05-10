"""
缠论策略V2 - 参数调优实验脚本 (subprocess独立进程版)

每组实验完全独立运行，无状态污染。

实验矩阵:
  组1: 杠杆倍数优化 (10x, 20x, 50x)
  组2: 最大加仓次数优化 (1, 2, 3, 4)
  组3: 投入比例优化 (5%, 10%, 15%, 20%)
  组4: 止损倍数优化 (紧->松 5档)
  组5: 分型窗口优化 (hg1: 5, 8, 12)

使用方法:
    python run_param_optimization.py
    python run_param_optimization.py --group 1
    python run_param_optimization.py --group 1_杠杆倍数,3_投入比例
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent

DATA_DIR = PROJECT_ROOT / "trading_system" / "data" / "binance_history"
BACKTEST_SCRIPT = PROJECT_ROOT / "trading_system" / "backtest" / "run_backtest.py"
OPT_RESULTS_DIR = DATA_DIR / "optimization_results"
OPT_REPORT_FILE = DATA_DIR / "optimization_report.json"


def get_date_range(days=90):
    today = datetime.now()
    end_date = today.strftime("%Y-%m-%d")
    start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    return start_date, end_date


BASELINE_PARAMS = {
    "symbol": "ETHUSDC",
    "interval": "30m",
    "initial_balance": 10000.0,
    "investment_ratio": 0.10,
    "leverage": 20,
    "long_stop_loss_multiplier": 1.50,
    "short_stop_loss_multiplier": 0.70,
    "hg1": 8,
    "max_add_positions": 3,
}

EXPERIMENTS = {
    "1_杠杆倍数": {
        "description": "杠杆倍数对收益和风险的影响",
        "variants": [
            {"name": "L1_10x",        "leverage": 10},
            {"name": "L2_20x_基线",   "leverage": 20},
            {"name": "L3_50x",        "leverage": 50},
        ],
    },
    "2_加仓次数": {
        "description": "最大加仓次数对资金利用率和风险的影响",
        "variants": [
            {"name": "A1_1次",        "max_add_positions": 1},
            {"name": "A2_2次",        "max_add_positions": 2},
            {"name": "A3_3次_基线",   "max_add_positions": 3},
            {"name": "A4_4次",        "max_add_positions": 4},
        ],
    },
    "3_投入比例": {
        "description": "每次投入比例对收益率和回撤的影响",
        "variants": [
            {"name": "R1_5%",         "investment_ratio": 0.05},
            {"name": "R2_10%_基线",   "investment_ratio": 0.10},
            {"name": "R3_15%",        "investment_ratio": 0.15},
            {"name": "R4_20%",        "investment_ratio": 0.20},
        ],
    },
    "4_止损倍数": {
        "description": "止损松紧度对胜率和盈亏比的影响",
        "variants": [
            {"name": "S1_极紧",       "long_stop_loss_multiplier": 1.30, "short_stop_loss_multiplier": 0.75},
            {"name": "S2_较紧",       "long_stop_loss_multiplier": 1.40, "short_stop_loss_multiplier": 0.72},
            {"name": "S3_基线",       "long_stop_loss_multiplier": 1.50, "short_stop_loss_multiplier": 0.70},
            {"name": "S4_较松",       "long_stop_loss_multiplier": 1.80, "short_stop_loss_multiplier": 0.60},
            {"name": "S5_极松",       "long_stop_loss_multiplier": 2.00, "short_stop_loss_multiplier": 0.50},
        ],
    },
    "5_分型窗口": {
        "description": "分型识别窗口大小对信号数量的影响",
        "variants": [
            {"name": "F1_hg5_敏感",   "hg1": 5},
            {"name": "F2_hg8_基线",   "hg1": 8},
            {"name": "F3_hg12_迟钝",  "hg1": 12},
        ],
    },
}

KEY_METRICS = [
    "total_return_pct",
    "max_drawdown_pct",
    "sharpe_ratio",
    "win_rate_pct",
    "profit_factor",
    "total_trades",
    "closed_trades",
    "net_profit",
    "avg_trade_profit",
    "avg_holding_hours",
    "max_consecutive_losses",
]


def build_cli_command(variant_params: Dict[str, Any], run_name: str) -> List[str]:
    """
    构建CLI命令

    Args:
        variant_params: 当前变体的完整参数字典
        run_name: 运行名称

    Returns:
        命令参数列表
    """
    start_date, end_date = get_date_range(days=90)
    results_file = f"opt_{run_name}.json"

    cmd = [
        sys.executable,
        str(BACKTEST_SCRIPT),
        "--symbol", str(variant_params["symbol"]),
        "--interval", str(variant_params["interval"]),
        "--initial-balance", str(variant_params["initial_balance"]),
        "--start-date", start_date,
        "--end-date", end_date,
        "--investment-ratio", str(variant_params["investment_ratio"]),
        "--leverage", str(variant_params["leverage"]),
        "--long-stop-loss-multiplier", str(variant_params["long_stop_loss_multiplier"]),
        "--short-stop-loss-multiplier", str(variant_params["short_stop_loss_multiplier"]),
        "--hg1", str(variant_params["hg1"]),
        "--strategy-version", "v2",
        "--max-add-positions", str(variant_params["max_add_positions"]),
        "--results-file", results_file,
    ]
    return cmd


def run_single_backtest(variant_params: Dict[str, Any], run_name: str) -> Optional[Dict[str, Any]]:
    """
    通过subprocess运行单次回测

    Args:
        variant_params: 当前变体的完整参数字典
        run_name: 运行名称

    Returns:
        回测结果字典，失败返回None
    """
    cmd = build_cli_command(variant_params, run_name)
    results_file = DATA_DIR / f"opt_{run_name}.json"

    print(f"\n  >>> [{run_name}] ", end="", flush=True)

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=600,
        )

        if result.returncode != 0:
            print(f"FAILED (exit={result.returncode})")
            stderr_tail = result.stderr.strip().split("\n")[-5:]
            for line in stderr_tail:
                print(f"      [ERR] {line}")
            return None

        if not results_file.exists():
            print(f"FAILED (no output file)")
            return None

        with open(results_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        ret = data.get("total_return_pct", "N/A")
        dd = data.get("max_drawdown_pct", "N/A")
        trades = data.get("total_trades", "N/A")
        print(f"OK | 收益={ret:.2f}% | 回撤={dd:.2f}% | 交易={trades}")

        return data

    except subprocess.TimeoutExpired:
        print("TIMEOUT")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def extract_summary(results: Dict[str, Any], params: Dict[str, Any], run_name: str) -> Dict[str, Any]:
    """提取关键指标摘要"""
    summary = {
        "name": run_name,
        "params": {
            "leverage": params.get("leverage"),
            "investment_ratio": params.get("investment_ratio"),
            "max_add_positions": params.get("max_add_positions"),
            "long_stop_loss_multiplier": params.get("long_stop_loss_multiplier"),
            "short_stop_loss_multiplier": params.get("short_stop_loss_multiplier"),
            "hg1": params.get("hg1"),
        },
    }
    for metric in KEY_METRICS:
        val = results.get(metric)
        summary[metric] = round(val, 4) if isinstance(val, float) else val

    return summary


def rank_summaries(summaries: List[Dict[str, Any]], key: str = "total_return_pct") -> List[Dict[str, Any]]:
    """按指定指标降序排列"""
    return sorted(
        [s for s in summaries if "error" not in s],
        key=lambda s: s.get(key, -99999) or -99999,
        reverse=True,
    )


def print_comparison_table(summaries: List[Dict[str, Any]], title: str):
    """打印分组对比表格"""
    ranked = rank_summaries(summaries)

    print(f"\n{'=' * 115}")
    print(f"  {title}")
    print(f"{'=' * 115}")

    header = (
        f"{'#':<3} {'实验名称':<16} {'收益率%':>8} {'回撤%':>8} {'夏普':>7} "
        f"{'胜率%':>7} {'盈利因子':>9} {'交易数':>7} {'净利$':>10} {'均利$':>8} {'连亏':>5} {'时H':>5}"
    )
    print(header)
    print("-" * 115)

    for i, s in enumerate(ranked, 1):
        if "error" in s:
            print(f"{i:<3} {s['name']:<16} {'  ERROR: ' + s['error']}")
            continue

        print(
            f"{i:<3} {s['name']:<16} "
            f"{s.get('total_return_pct', 0) or 0:>8.2f} "
            f"{s.get('max_drawdown_pct', 0) or 0:>8.2f} "
            f"{s.get('sharpe_ratio', 0) or 0:>7.2f} "
            f"{s.get('win_rate_pct', 0) or 0:>7.2f} "
            f"{s.get('profit_factor', 0) or 0:>9.2f} "
            f"{s.get('total_trades', 0) or 0:>7} "
            f"{s.get('net_profit', 0) or 0:>10.2f} "
            f"{s.get('avg_trade_profit', 0) or 0:>8.2f} "
            f"{s.get('max_consecutive_losses', 0) or 0:>5} "
            f"{s.get('avg_holding_hours', 0) or 0:>5.1f}"
        )

    print("-" * 115)

    if ranked:
        best = ranked[0]
        print(f"  >> 最优: {best['name']} "
              f"(收益={best.get('total_return_pct', 0):.2f}%, "
              f"夏普={best.get('sharpe_ratio', 0):.2f}, "
              f"回撤={best.get('max_drawdown_pct', 0):.2f}%)")


def generate_full_report(all_results: Dict[str, List[Dict[str, Any]]]):
    """生成完整对比报告"""
    print(f"\n\n{'#' * 115}")
    print(f"{'#' * 115}")
    print(f"    缠论策略V2 参数优化实验 - 完整报告")
    print(f"    基线: 投入10% | 杠杆20x | 加仓3次 | 止损1.50/0.70 | hg1=8")
    print(f"    时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#' * 115}")
    print(f"{'#' * 115}")

    all_summaries = []
    for group_id, summaries in all_results.items():
        group_config = EXPERIMENTS.get(group_id, {})
        desc = group_config.get("description", group_id)
        print_comparison_table(summaries, f"组{group_id}: {desc}")
        all_summaries.extend(summaries)

    print_comparison_table(all_summaries, "综合排名 (按总收益率)")

    ranked_all = rank_summaries(all_summaries)

    print(f"\n{'=' * 115}")
    print("  参数优化建议")
    print(f"{'=' * 115}")

    if ranked_all:
        best = ranked_all[0]
        print(f"\n  1. 最高收益组合: {best['name']}")
        print(f"     收益率={best.get('total_return_pct', 0):.2f}% | "
              f"回撤={best.get('max_drawdown_pct', 0):.2f}% | "
              f"夏普={best.get('sharpe_ratio', 0):.2f}")
        print(f"     参数: {json.dumps(best.get('params', {}), ensure_ascii=False)}")

    safe_ranked = rank_summaries(all_summaries, key="sharpe_ratio")
    if safe_ranked:
        best_safe = safe_ranked[0]
        print(f"\n  2. 最高夏普组合: {best_safe['name']}")
        print(f"     夏普={best_safe.get('sharpe_ratio', 0):.2f} | "
              f"收益率={best_safe.get('total_return_pct', 0):.2f}% | "
              f"回撤={best_safe.get('max_drawdown_pct', 0):.2f}%")

    low_dd = sorted(
        [s for s in ranked_all if (s.get("max_drawdown_pct") or 999) < 20],
        key=lambda s: s.get("total_return_pct", -9999) or -9999,
        reverse=True,
    )
    if low_dd:
        best_low_dd = low_dd[0]
        print(f"\n  3. 低回撤(<20%)最优: {best_low_dd['name']}")
        print(f"     收益率={best_low_dd.get('total_return_pct', 0):.2f}% | "
              f"回撤={best_low_dd.get('max_drawdown_pct', 0):.2f}% | "
              f"夏普={best_low_dd.get('sharpe_ratio', 0):.2f}")

    print(f"\n  4. 各维度最优:")
    for group_id, summaries in all_results.items():
        if not summaries:
            continue
        ranked_g = rank_summaries(summaries)
        if ranked_g:
            best_g = ranked_g[0]
            print(f"     {group_id}: {best_g['name']} "
                  f"(收益={best_g.get('total_return_pct', 0):.2f}%, "
                  f"夏普={best_g.get('sharpe_ratio', 0):.2f})")

    return ranked_all


def run_experiment_group(group_id: str, group_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """运行一组实验的所有变体"""
    print(f"\n{'=' * 70}")
    print(f"  实验组: {group_id} - {group_config['description']}")
    print(f"{'=' * 70}")

    summaries = []

    for variant in group_config["variants"]:
        params = BASELINE_PARAMS.copy()
        params.update({k: v for k, v in variant.items() if k != "name"})
        run_name = variant["name"]

        for k, v in variant.items():
            if k != "name":
                print(f"     {k} = {v}")

        try:
            results = run_single_backtest(params, run_name)
            if results:
                summary = extract_summary(results, params, run_name)
                summaries.append(summary)
            else:
                summaries.append({"name": run_name, "error": "SUBPROCESS_FAILED", "params": params})
        except Exception as e:
            summaries.append({"name": run_name, "error": str(e), "params": params})

    return summaries


def clean_old_results():
    """清理旧的优化结果文件"""
    for f in DATA_DIR.glob("opt_*.json"):
        try:
            f.unlink()
        except Exception:
            pass


def parse_args():
    parser = argparse.ArgumentParser(description="缠论策略V2 - 参数优化实验 (subprocess版)")
    parser.add_argument(
        "--group",
        type=str,
        default=None,
        help="运行指定实验组,逗号分隔 (如: 1_杠杆倍数,3_投入比例). 默认全部5组",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="运行前清理旧的优化结果文件",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    OPT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.clean:
        clean_old_results()
        print("已清理旧的优化结果文件")

    if args.group:
        group_ids = [g.strip() for g in args.group.split(",")]
        selected = {}
        for gid in group_ids:
            if gid in EXPERIMENTS:
                selected[gid] = EXPERIMENTS[gid]
        if not selected:
            available = list(EXPERIMENTS.keys())
            print(f"错误: 无效的实验组 '{args.group}'")
            print(f"可选: {available}")
            sys.exit(1)
    else:
        selected = EXPERIMENTS

    total_variants = sum(len(g["variants"]) for g in selected.values())

    print(f"\n{'#' * 70}")
    print(f"  缠论策略V2 - 参数优化实验")
    print(f"  基线: 投入10% | 杠杆20x | 加仓3次 | 止损1.50/0.70 | hg1=8")
    print(f"  实验组: {len(selected)} | 总变体: {total_variants}")
    print(f"  模式: subprocess独立进程 (无状态污染)")
    print(f"{'#' * 70}")

    start_time = time.time()
    all_results = {}

    group_order = sorted(selected.keys())
    for group_id in group_order:
        group_config = selected[group_id]
        summaries = run_experiment_group(group_id, group_config)
        all_results[group_id] = summaries

    elapsed = time.time() - start_time

    ranked_all = generate_full_report(all_results)

    report_data = {
        "report_time": datetime.now().isoformat(),
        "baseline_params": BASELINE_PARAMS,
        "data_range": f"{get_date_range(90)[0]} ~ {get_date_range(90)[1]}",
        "elapsed_seconds": round(elapsed, 1),
        "total_variants": total_variants,
        "group_results": {gid: summaries for gid, summaries in all_results.items()},
        "overall_ranking": [
            {
                "rank": i + 1,
                "name": s["name"],
                "total_return_pct": s.get("total_return_pct"),
                "max_drawdown_pct": s.get("max_drawdown_pct"),
                "sharpe_ratio": s.get("sharpe_ratio"),
                "params": s.get("params"),
            }
            for i, s in enumerate(ranked_all)
            if "error" not in s
        ],
    }

    with open(OPT_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 70}")
    print(f"  报告已保存: {OPT_REPORT_FILE}")
    print(f"  总耗时: {elapsed:.1f} 秒 ({elapsed/60:.1f} 分)")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()