import os
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ==============================================================================
# 1. GOOGLE SHEETS CONFIGURATION
# ==============================================================================
# Read from environment variable to keep credentials out of version control
SHEET_CSV_URL = os.getenv(
    "SHEET_CSV_URL",
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vSaPToc3xnwH3RgkfTc5zzXb5cEMyrdeTJoSERr73IkWcioxlZc3nTSMPYk0qoOMMN8K6S1RYgplKJr/pub?gid=0&single=true&output=csv",
)


def load_sheet_data(url):
    """Loads Google Sheet directly via published CSV link, falling back to local file if necessary."""
    try:
        df = pd.read_csv(url)
        print("[+] Successfully fetched live data from Google Sheets.")
        return df
    except Exception as e:
        print(f"[!] Could not fetch live Google Sheet ({e}).")
        print("[!] Attempting to load 'master_gradebook.csv' from local directory...")
        if os.path.exists("master_gradebook.csv"):
            return pd.read_csv("master_gradebook.csv")
        else:
            raise FileNotFoundError(
                "No live spreadsheet URL or local 'master_gradebook.csv' found!"
            )


# ==============================================================================
# 2. VIKING POLL MATH ENGINE
# ==============================================================================
def calculate_viking_poll(score_a, score_b, base_undecided=0.04, moe=2.4):
    """Transforms raw sim point totals into Viking Poll Service polling numbers."""
    total_pts = score_a + score_b
    if total_pts == 0:
        raw_diff = 0
    else:
        raw_diff = (score_a - score_b) / total_pts

    # Tanh curve compresses large gaps into realistic polling spreads
    dampened_lead = np.tanh(raw_diff * 1.5) * 0.14
    decided_pool = 1.0 - base_undecided  # 0.96

    poll_a = round(((decided_pool / 2) + dampened_lead) * 100, 1)
    poll_b = round(((decided_pool / 2) - dampened_lead) * 100, 1)
    undecided = max(0.0, round(100.0 - (poll_a + poll_b), 1))

    return poll_a, poll_b, undecided, moe


# ==============================================================================
# 3. GRAPHIC DASHBOARD GENERATOR
# ==============================================================================
def generate_viking_poll_dashboard(df, output_img="viking_poll_dashboard.png"):
    grouped = df.groupby("district")
    num_districts = len(grouped)

    fig, axes = plt.subplots(
        num_districts, 1, figsize=(9.5, 2.7 * num_districts)
    )
    if num_districts == 1:
        axes = [axes]

    for idx, (district_name, group) in enumerate(grouped):
        ax = axes[idx]
        rows = group.to_dict(orient="records")

        if not rows:
            continue

        cand_a = f"{rows[0]['candidate']} ({rows[0]['party']})"
        score_a = rows[0]["total sim points"]

        if len(rows) > 1:
            cand_b = f"{rows[1]['candidate']} ({rows[1]['party']})"
            score_b = rows[1]["total sim points"]
        else:
            cand_b = "Opponent (IND)"
            score_b = 0

        p_a, p_b, und, moe = calculate_viking_poll(score_a, score_b)

        categories = [cand_a, cand_b, "Undecided / Other"]
        percents = [p_a, p_b, und]
        colors = ["#1a5276", "#a93226", "#7f8c8d"]
        xerr = [moe, moe, 0.0]

        y_pos = [2, 1, 0]
        bars = ax.barh(
            y_pos,
            percents,
            xerr=xerr,
            color=colors,
            height=0.48,
            alpha=0.9,
            edgecolor="black",
            error_kw=dict(
                ecolor="black", lw=1.5, capsize=5, capthick=1.5
            ),
        )

        ax.set_yticks(y_pos)
        ax.set_yticklabels(categories, fontsize=10, fontweight="bold")
        ax.set_xlim(0, 70)
        ax.set_xlabel("Voter Preference (%)", fontsize=9, fontweight="bold")
        ax.set_title(
            f"Viking Poll Service — {district_name} (MoE: ±{moe}% | Sample: n=400 Likely Voters)",
            fontsize=11,
            fontweight="bold",
            pad=10,
        )

        for bar, pct in zip(bars, percents):
            width = bar.get_width()
            err_offset = moe if width in (p_a, p_b) else 0
            ax.text(
                width + err_offset + 1.2,
                bar.get_y() + bar.get_height() / 2,
                f"{pct:.1f}%",
                va="center",
                ha="left",
                fontsize=9,
                fontweight="bold",
            )

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_img, dpi=300)
    plt.close()
    print(f"[+] Poll Summary Graphic created: {output_img}")


# ==============================================================================
# 4. HTML WEBSITE GENERATOR
# ==============================================================================
def generate_html_website(df, output_html="index.html"):
    cards_html = ""
    grouped = df.groupby("district")

    for district_name, group in grouped:
        rows = group.to_dict(orient="records")
        if not rows:
            continue

        cand_a_name = rows[0]["candidate"]
        cand_a_party = rows[0]["party"]
        score_a = rows[0]["total sim points"]

        if len(rows) > 1:
            cand_b_name = rows[1]["candidate"]
            cand_b_party = rows[1]["party"]
            score_b = rows[1]["total sim points"]
        else:
            cand_b_name, cand_b_party, score_b = "Opponent", "IND", 0

        p_a, p_b, und, moe = calculate_viking_poll(score_a, score_b)
        margin = abs(p_a - p_b)

        if margin <= moe:
            status = "<span style='color: #d9534f; font-weight: bold;'>Statistical Dead Heat (Within MoE)</span>"
        elif p_a > p_b:
            status = f"<span style='color: #1a5276; font-weight: bold;'>{cand_a_name} Leads (+{margin:.1f}%)</span>"
        else:
            status = f"<span style='color: #a93226; font-weight: bold;'>{cand_b_name} Leads (+{margin:.1f}%)</span>"

        cards_html += f"""
        <div style="background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; margin-bottom: 24px; box-shadow: 0 2px 6px rgba(0,0,0,0.06);">
            <h2 style="margin-top:0; color: #1b2a4a; border-bottom: 2px solid #3498db; padding-bottom: 8px; font-size: 20px;">
                Viking Poll Service — {district_name}
            </h2>
            <p style="font-size: 14px; color: #444; margin-bottom: 16px;">
                <strong>Race Assessment:</strong> {status} &nbsp;|&nbsp; <strong>MoE:</strong> ±{moe}%
            </p>
            
            <!-- Candidate A -->
            <div style="margin-bottom: 14px;">
                <div style="display:flex; justify-content:space-between; font-weight:bold; font-size:14px; color: #2c3e50;">
                    <span>{cand_a_name} ({cand_a_party})</span><span>{p_a}%</span>
                </div>
                <div style="background:#e9ecef; border-radius:4px; height:24px; width:100%; overflow:hidden; margin-top:4px;">
                    <div style="background:#1a5276; width:{p_a}%; height:100%;"></div>
                </div>
            </div>
            
            <!-- Candidate B -->
            <div style="margin-bottom: 14px;">
                <div style="display:flex; justify-content:space-between; font-weight:bold; font-size:14px; color: #2c3e50;">
                    <span>{cand_b_name} ({cand_b_party})</span><span>{p_b}%</span>
                </div>
                <div style="background:#e9ecef; border-radius:4px; height:24px; width:100%; overflow:hidden; margin-top:4px;">
                    <div style="background:#a93226; width:{p_b}%; height:100%;"></div>
                </div>
            </div>

            <!-- Undecided -->
            <div>
                <div style="display:flex; justify-content:space-between; font-size:13px; color:#666;">
                    <span>Undecided / Other</span><span>{und}%</span>
                </div>
                <div style="background:#e9ecef; border-radius:4px; height:18px; width:100%; overflow:hidden; margin-top:4px;">
                    <div style="background:#7f8c8d; width:{und}%; height:100%;"></div>
                </div>
            </div>
        </div>
        """

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Viking Poll Service — Election Tracking Center</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; background: #f4f6f9; margin:0; padding: 24px; color: #333; }}
        .container {{ max-width: 820px; margin: 0 auto; }}
        .header {{ text-align: center; margin-bottom: 32px; background: #1b2a4a; color: white; padding: 24px; border-radius: 8px; }}
        .header h1 {{ margin: 0; font-size: 26px; letter-spacing: 0.5px; }}
        .header p {{ color: #cbd5e1; font-size: 14px; margin-top: 6px; margin-bottom: 0; }}
        .footer {{ text-align: center; font-size: 12px; color: #888; margin-top: 40px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🛡️ Viking Poll Service</h1>
            <p>Official Election Tracking Center | Non-Partisan Polling Model</p>
        </div>
        {cards_html}
        <div class="footer">
            <p>Methodology: Random sample of n=400 likely voters per district. Margin of Error ±2.4% at 95% confidence level.</p>
        </div>
    </div>
</body>
</html>
"""
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(full_html)
    print(f"[+] Live HTML Website file generated: {output_html}")


# Execution block
if __name__ == "__main__":
    df_data = load_sheet_data(SHEET_CSV_URL)
    generate_viking_poll_dashboard(df_data)
    generate_html_website(df_data)
