"""시뮬레이터 연구용 최종 스코어 그래프. 웹/API와 연결하지 않는다."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import csv
import math
import re


def ordered_score_counts(distribution: list[dict], order: str) -> list[tuple[int, int, int]]:
    """실제로 발생한 스코어를 빈도순 또는 합계득점순으로 정렬한다."""
    counts = {(r["team_a_score"], r["team_b_score"]): r["count"] for r in distribution}
    if not counts:
        raise ValueError("그래프에 표시할 경기 결과가 없습니다.")
    if order == "frequency":
        return [(a, b, count) for (a, b), count in sorted(
            counts.items(), key=lambda item: (-item[1], sum(item[0]), item[0][0]),
        )]
    if order != "score":
        raise ValueError("정렬 방식은 frequency 또는 score여야 합니다.")
    return [
        (a, b, count)
        for (a, b), count in sorted(counts.items(), key=lambda item: (sum(item[0]), item[0][0]))
        if count > 0
    ]


def plot_match_scores(
    result: dict,
    team_a_name: str,
    team_b_name: str,
    output_dir: Path | str | None = None,
    show: bool = True,
    order: str = "both",
    context: str = "",
) -> list[Path]:
    """각 그래프를 PNG로 저장하고, 창을 하나씩 표시한다. 첫 창을 닫으면 다음 창이 열린다."""
    if order not in ("both", "frequency", "score"):
        raise ValueError("정렬 방식은 both, frequency, score 중 하나여야 합니다.")
    distribution = result["score_distribution"]
    n_games = result["n_games"]
    if n_games < 1 or sum(r["count"] for r in distribution) != n_games:
        raise ValueError("스코어별 횟수 합계가 시뮬레이션 횟수와 일치해야 합니다.")

    # API나 로그 시뮬레이션만 사용할 때는 그래프 라이브러리가 필요하지 않다.
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.patches import Patch
    from matplotlib.ticker import MaxNLocator, StrMethodFormatter

    available_fonts = {font.name for font in font_manager.fontManager.ttflist}
    font = next((name for name in ("Malgun Gothic", "AppleGothic", "NanumGothic") if name in available_fonts), "DejaVu Sans")
    output_dir = Path(output_dir) if output_dir is not None else Path(__file__).parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_match = re.sub(r'[<>:"/\\|?*\s]+', "_", f"{team_a_name}_vs_{team_b_name}").strip("._") or "match"
    prefix = f"{safe_match}_{datetime.now():%Y%m%d_%H%M%S_%f}"
    colors = ("#e97824", "#858b98", "#337bd4")
    wins_a = result["team_a"]["wins"]
    wins_b = result["team_b"]["wins"]
    summary = (
        f"{n_games:,}경기  |  {team_a_name} 승 {wins_a / n_games:.2%}  ·  "
        f"무승부 {result['draws'] / n_games:.2%}  ·  {team_b_name} 승 {wins_b / n_games:.2%}"
    )
    paths = []

    with plt.rc_context({"font.family": font, "axes.unicode_minus": False}):
        for sort_order in (("frequency", "score") if order == "both" else (order,)):
            rows = [row for row in ordered_score_counts(distribution, sort_order) if row[2] >= 50]
            if sort_order == "frequency":
                rows = rows[:10]
            labels = [f"{a}:{b}" for a, b, _ in rows]
            counts = [count for _, _, count in rows]
            bar_colors = [colors[0] if a > b else colors[2] if a < b else colors[1] for a, b, _ in rows]
            fig, ax = plt.subplots(figsize=(20, 8))
            title = "최종 스코어별 발생 횟수 — 빈도순" if sort_order == "frequency" else "최종 스코어별 발생 횟수 — 합계 득점순"
            fig.canvas.manager.set_window_title(title)
            fig.patch.set_facecolor("#f7f9fc")
            ax.set_facecolor("#ffffff")
            ax.bar(range(len(rows)), counts, color=bar_colors, width=0.86, zorder=3)
            ax.set_xlim(-0.8, max(1, len(rows)) - 0.2)
            ax.set_ylim(0, max(1, max(counts, default=0)) * 1.18)
            if not rows:
                ax.text(0.5, 0.5, "50회 이상 발생한 스코어가 없습니다.", transform=ax.transAxes,
                        ha="center", va="center", color="#64748b")
            ax.set_ylabel("발생 횟수 (경기)")
            ax.set_xlabel(f"최종 스코어 ({team_a_name} : {team_b_name})", labelpad=12)
            ax.yaxis.set_major_locator(MaxNLocator(integer=True))
            ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
            ax.grid(axis="y", color="#dfe5ed", zorder=0)
            ax.spines[["top", "right"]].set_visible(False)
            fig.suptitle(f"{team_a_name} vs {team_b_name}\n{title}", fontsize=19, fontweight="bold", y=0.98)
            ax.set_title(summary, fontsize=11, pad=28)
            ax.legend(handles=[Patch(color=c, label=label) for c, label in zip(
                colors, (f"{team_a_name} 승", "무승부", f"{team_b_name} 승"),
            )], loc="upper right", frameon=False, ncol=3)

            # 전체 이미지에서는 라벨을 간격 표시하고, 확대하면 해당 구간의 스코어를 촘촘히 표시한다.
            def update_ticks(axis, score_labels=labels):
                left, right = axis.get_xlim()
                start = max(0, math.ceil(left))
                stop = min(len(score_labels) - 1, math.floor(right))
                step = max(1, math.ceil((stop - start + 1) / 36))
                indices = list(range(start, stop + 1, step))
                if start == 0 and step == 1:
                    indices = sorted(set(indices + list(range(min(6, len(score_labels))))))
                axis.set_xticks(indices, [score_labels[i] for i in indices], rotation=70, ha="right", fontsize=8)

            update_ticks(ax)
            ax.callbacks.connect("xlim_changed", update_ticks)

            # 막대 위에 마우스를 올리면 생략된 축 라벨과 횟수·비율을 정확하게 확인한다.
            annotation = ax.annotate("", xy=(0, 0), xytext=(14, 20), textcoords="offset points",
                                     bbox={"boxstyle": "round", "fc": "white", "ec": "#b6c2d2"}, zorder=5)
            annotation.set_visible(False)

            def hover(event, chart=ax, note=annotation, data=rows, canvas=fig.canvas):
                if event.inaxes != chart or event.xdata is None:
                    if note.get_visible():
                        note.set_visible(False)
                        canvas.draw_idle()
                    return
                index = round(event.xdata)
                if not 0 <= index < len(data):
                    return
                a, b, count = data[index]
                note.xy = (index, count)
                note.set_text(f"{team_a_name} {a} : {b} {team_b_name}\n{count:,}회 ({count / n_games:.2%})")
                note.set_visible(True)
                canvas.draw_idle()

            fig.canvas.mpl_connect("motion_notify_event", hover)
            # 콜백이 창 수명 동안 유지되도록 참조를 보관한다.
            fig._score_hover = hover
            description = (
                f"50회 이상 발생한 스코어 중 상위 {len(rows):,}개 표시 (최대 10개) · 발생 횟수 내림차순"
                if sort_order == "frequency" else
                f"50회 이상 발생한 {len(rows):,}가지 스코어 표시 · 합계 득점, 원정 득점 오름차순"
            )
            fig.text(0.06, 0.055, description, fontsize=10, color="#475569")
            fig.text(0.06, 0.025, f"실제 모의경기 관측 분포 (정규분포 보정 없음) · 끝내기/최대 12회 연장 반영{(' · ' + context) if context else ''}",
                     fontsize=9, color="#64748b")
            fig.subplots_adjust(left=0.06, right=0.98, top=0.79, bottom=0.23)
            path = output_dir / f"{prefix}_{sort_order}.png"
            fig.savefig(path, dpi=180, facecolor=fig.get_facecolor())
            paths.append(path.resolve())
            try:
                if show:
                    plt.show(block=True)
            finally:
                plt.close(fig)
    return paths


def show_frequency_table(
    result: dict,
    team_a_name: str,
    team_b_name: str,
    output_dir: Path | str | None = None,
    show: bool = True,
    page_size: int = 25,
) -> list[Path]:
    """빈도순 전체 CSV와 첫 페이지 PNG를 저장하고, 표 창에서는 모든 페이지를 볼 수 있다."""
    if page_size < 1:
        raise ValueError("페이지당 행 수는 1 이상이어야 합니다.")
    rows = ordered_score_counts(result["score_distribution"], "frequency")
    n_games = result["n_games"]
    if n_games < 1 or sum(count for _, _, count in rows) != n_games:
        raise ValueError("스코어별 횟수 합계가 시뮬레이션 횟수와 일치해야 합니다.")
    output_dir = Path(output_dir) if output_dir is not None else Path(__file__).parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_match = re.sub(r'[<>:"/\\|?*\s]+', "_", f"{team_a_name}_vs_{team_b_name}").strip("._") or "match"
    prefix = f"{safe_match}_{datetime.now():%Y%m%d_%H%M%S_%f}_frequency_table"
    csv_path = output_dir / f"{prefix}.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["순위", f"{team_a_name} 득점", f"{team_b_name} 득점", "횟수", "비율 (%)"])
        writer.writerows((rank, a, b, count, f"{count / n_games * 100:.4f}")
                         for rank, (a, b, count) in enumerate(rows, 1))

    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.widgets import Button

    available_fonts = {font.name for font in font_manager.fontManager.ttflist}
    font = next((name for name in ("Malgun Gothic", "AppleGothic", "NanumGothic") if name in available_fonts), "DejaVu Sans")
    pages = math.ceil(len(rows) / page_size)
    paths = [csv_path.resolve()]
    with plt.rc_context({"font.family": font, "axes.unicode_minus": False}):
        fig, ax = plt.subplots(figsize=(12, 10))
        fig.canvas.manager.set_window_title("빈도순 최종 스코어 표")
        fig.patch.set_facecolor("#f7f9fc")
        fig.subplots_adjust(left=0.04, right=0.96, top=0.88, bottom=0.13)
        page = [0]

        def draw_page(index):
            ax.clear()
            ax.axis("off")
            start = index * page_size
            visible_rows = rows[start:start + page_size]
            contents = [
                [str(start + offset + 1), f"{a}:{b}", f"{count:,}", f"{count / n_games:.2%}",
                 f"{team_a_name} 승" if a > b else f"{team_b_name} 승" if a < b else "무승부"]
                for offset, (a, b, count) in enumerate(visible_rows)
            ]
            table = ax.table(cellText=contents, colLabels=["순위", f"스코어 ({team_a_name} : {team_b_name})", "횟수", "비율", "결과"],
                             cellLoc="center", colWidths=[0.10, 0.32, 0.18, 0.16, 0.24], loc="upper center")
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            for (row, _column), cell in table.get_celld().items():
                cell.set_height(0.90 / (min(page_size, len(rows)) + 1))
                cell.set_edgecolor("#dce3ed")
                cell.set_facecolor("#24364d" if row == 0 else "#ffffff" if row % 2 else "#eaf0f7")
                if row == 0:
                    cell.get_text().set_color("white")
                    cell.get_text().set_weight("bold")
            fig.suptitle(f"{team_a_name} vs {team_b_name} · 빈도순 최종 스코어 표", fontsize=17, fontweight="bold", y=0.97)
            ax.set_title(f"전체 {n_games:,}경기 · {len(rows):,}가지 스코어 · {index + 1}/{pages}페이지", fontsize=11, pad=15)
            fig.canvas.draw_idle()

        try:
            draw_page(0)
            path = output_dir / f"{prefix}_01.png"
            fig.savefig(path, dpi=180, facecolor=fig.get_facecolor())
            paths.append(path.resolve())
            if show:
                previous = Button(fig.add_axes([0.32, 0.04, 0.15, 0.04]), "이전 페이지")
                following = Button(fig.add_axes([0.53, 0.04, 0.15, 0.04]), "다음 페이지")

                def move_page(delta):
                    page[0] = max(0, min(pages - 1, page[0] + delta))
                    draw_page(page[0])

                previous.on_clicked(lambda _event: move_page(-1))
                following.on_clicked(lambda _event: move_page(1))
                plt.show(block=True)
        finally:
            plt.close(fig)
    return paths
