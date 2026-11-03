"""Charts of the benchmark results (needs matplotlib)."""

from pathlib import Path

from car_catalog.profiling import BenchmarkRecord, load_records_csv


def make_all(directory: Path) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    methods = load_records_csv(directory / "benchmark_results.csv")
    scaling = load_records_csv(directory / "worker_scaling.csv")
    created = []

    # 1. execution time by method and size
    sizes = sorted({r.data_size for r in methods})
    names = list(dict.fromkeys(r.method for r in methods))
    fig, ax = plt.subplots(figsize=(9.5, 4.5))
    width = 0.8 / len(names)
    for index, name in enumerate(names):
        values = [
            next((r.mean_time for r in methods
                  if r.method == name and r.data_size == s), 0.0)
            for s in sizes
        ]
        positions = [i + index * width for i in range(len(sizes))]
        ax.bar(positions, values, width, label=name)
    ax.set_xticks([i + 0.4 - width / 2 for i in range(len(sizes))])
    ax.set_xticklabels([f"{s:,}" for s in sizes])
    ax.set_yscale("log")
    ax.set_xlabel("number of cars")
    ax.set_ylabel("mean time, s (log scale)")
    ax.set_title("Manufacturer statistics: execution time")
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = directory / "execution_time.png"
    fig.savefig(path, dpi=130)
    plt.close(fig)
    created.append(path)

    # 2. speedup versus number of workers
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for kind in ("Threads", "Processes"):
        rows: list[BenchmarkRecord] = sorted(
            (
                r for r in scaling
                if r.method == kind and r.experiment == "scaling"
            ),
            key=lambda r: r.workers,
        )
        ax.plot([r.workers for r in rows], [r.speedup for r in rows],
                marker="o", label=kind)
    ax.axhline(1.0, color="gray", linestyle="--", linewidth=1)
    ax.set_xlabel("workers")
    ax.set_ylabel("speedup (sequential time / time)")
    ax.set_title("Speedup versus number of workers")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    path = directory / "speedup_workers.png"
    fig.savefig(path, dpi=130)
    plt.close(fig)
    created.append(path)
    return created
