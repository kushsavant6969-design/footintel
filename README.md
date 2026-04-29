# FootIntel

Fan segmentation and lifetime value analysis for football clubs.

Upload a CSV of fan data → get instant engagement, commercial, and loyalty scores → identify high-value, at-risk, and dormant segments → download actionable reports.

## Features

- **Auto age segmentation** — Child, Young Adult, Adult, Senior
- **Three scores per fan (0–100)**
  - Engagement: app opens, email opens, article views, in-app clicks
  - Commercial: total revenue, purchase recency (exponential decay), frequency
  - Loyalty: tenure in database, purchase diversity, consistency
- **Eight behavioural segments** — Champions, Loyal Fans, High Potential, Rising Stars, At Risk, Dormant, Win Back, Casual
- **Interactive dashboard** — scatter landscape, donut, age heatmap, radar charts
- **Per-segment recommendations** with specific retention actions
- **Downloadable reports** — full fan data CSV, segment summary CSV, age breakdown CSV

## CSV format

| Column | Description |
|--------|-------------|
| User_ID | Unique fan identifier |
| Age | Integer |
| Gender | M / F / Non-binary |
| Country | String |
| App_Opens | Integer |
| Email_Opens | Integer |
| Article_Views | Integer |
| In_App_Clicks | Integer |
| Ticket_Purchases | Integer |
| Membership_Purchases | Integer |
| Retail_Purchases | Integer |
| Total_Revenue | Float (£) |
| Last_Purchase_Date | YYYY-MM-DD |
| Join_Date | YYYY-MM-DD |

Missing columns are handled gracefully with neutral score fallbacks. Download the sample CSV inside the app to get started.

## Run locally

```bash
pip install -r requirements.txt
streamlit run footintel.py
```

## Deploy to Render

Connect this repository to Render — the `render.yaml` handles the rest.
