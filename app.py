import streamlit as st
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread.exceptions import WorksheetNotFound, APIError

# ========== CONFIG ==========
SHEET_NAME = "Diet Logging"
MEALS_SHEET = "Meals"
GOALS_SHEET = "Goals"
NOTES_SHEET = "Daily_Notes"

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# ========== AUTHENTICATION ==========
try:
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open(SHEET_NAME)
    st.success(f"✅ Connected to spreadsheet: {SHEET_NAME}")
except KeyError:
    st.error("❌ Secret 'gcp_service_account' not found in Streamlit secrets.")
    st.stop()
except APIError as e:
    st.error(f"❌ APIError: Could not access the spreadsheet. Check sharing and credentials.\n{e}")
    st.stop()
except Exception as e:
    st.error(f"❌ Unexpected error during Google Sheets authentication:\n{e}")
    st.stop()

# ========== HELPER ==========
def ensure_worksheet(name, header):
    """Ensure a worksheet exists; create if missing."""
    try:
        ws = spreadsheet.worksheet(name)
    except WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=name, rows="1000", cols="20")
        # Add header row
        ws.append_row(header)
        st.info(f"ℹ️ Worksheet '{name}' created with headers.")
    return spreadsheet.worksheet(name)

# ========== WORKSHEETS ==========
meals_ws = ensure_worksheet(MEALS_SHEET,
    ["date", "time", "food_name", "grams", "protein_g", "carbs_g", "fat_g", "calories", "daily_calorie_goal", "daily_protein_goal", "notes"])
goals_ws = ensure_worksheet(GOALS_SHEET, ["month_year","calorie_goal","protein_goal","created_at"])
notes_ws = ensure_worksheet(NOTES_SHEET, ["date","note","created_at"])

# ========== UI ==========
st.title("🍽️ Diet Tracker")
st.markdown("Enter each food you eat (one row per food) — it auto-saves to Google Sheets.")

# Left column: quick food entry
col1, col2 = st.columns([2,1])
with col1:
    entry_date = st.date_input("📅 Date", datetime.date.today())
    entry_time = st.time_input("⏰ Time eaten", datetime.datetime.now().time())
    food_item = st.text_input("🍲 Food item (free text) e.g., 'Cooked rice'")
    qty = st.number_input("⚖️ Quantity (g) — enter grams", min_value=0.0, value=100.0, step=1.0)
    calories = st.number_input("🔥 Calories (kcal)", min_value=0.0, value=200.0, step=0.1)
    protein = st.number_input("💪 Protein (g)", min_value=0.0, value=20.0, step=0.1)
    carbs = st.number_input("🥖 Carbs (g)", min_value=0.0, value=30.0, step=0.1)
    fat = st.number_input("🧈 Fat (g)", min_value=0.0, value=5.0, step=0.1)
    entry_notes = st.text_area("📝 Notes for this entry (optional)", value="", max_chars=500)

with col2:
    st.markdown("### 📊 Quick Actions")
    st.write("Auto-save: each `Add Food` saves that food row right away.")
    add_btn = st.button("➕ Add Food (Auto-Save)")
    st.markdown("---")
    st.markdown("### 🎯 Monthly Goals")
    today = datetime.date.today()
    month_year_label = st.selectbox(
        "Select month (change to create/update goal)",
        options=[(today - datetime.timedelta(days=30*i)).strftime("%Y-%m") for i in range(0,12)],
        index=0
    )
    calorie_goal_input = st.number_input("Daily calorie goal (kcal)", min_value=500, value=1700, step=50)
    protein_goal_input = st.number_input("Daily protein goal (g)", min_value=0, value=80, step=5)
    set_goal_btn = st.button("💾 Set / Update Monthly Goal")

st.markdown("---")

# ========== GOALS LOGIC ==========
def upsert_goal(ws, month_label, cal_goal, prot_goal):
    records = ws.get_all_records()
    for i, r in enumerate(records, start=2):
        if r.get("month_year") == month_label:
            ws.update(f"B{i}", cal_goal)
            ws.update(f"C{i}", prot_goal)
            ws.update(f"D{i}", datetime.datetime.now().isoformat())
            return "updated"
    ws.append_row([month_label, cal_goal, prot_goal, datetime.datetime.now().isoformat()])
    return "created"

if set_goal_btn:
    result = upsert_goal(goals_ws, month_year_label, calorie_goal_input, protein_goal_input)
    st.success(f"Goal {result} for {month_year_label}: {calorie_goal_input} kcal/day, {protein_goal_input} g protein/day")

# ========== AUTO-SAVE FOOD ENTRY ==========
def append_meal_row(ws, row):
    ws.append_row(row)

if add_btn:
    if not food_item:
        st.warning("Please enter a food name.")
    else:
        row = [
    entry_date.strftime("%Y-%m-%d"),  # date
    entry_time.strftime("%H:%M:%S"),  # time
    food_item,                         # food_name
    round(qty,1),                      # grams
    round(protein,1),                  # protein_g
    round(carbs,1),                    # carbs_g
    round(fat,1),                      # fat_g
    round(calories,1),                 # calories
    calorie_goal_input,                # daily_calorie_goal
    protein_goal_input,                # daily_protein_goal
    entry_notes                        # notes
]

        try:
            append_meal_row(meals_ws, row)
            st.success(f"Saved: {food_item} ({row[2]} at {row[1]})")
        except Exception as e:
            st.error(f"Save failed: {e}")

# ========== DAILY SUMMARY & CHECKS ==========
st.markdown("## 📅 Daily Summary")
summary_date = st.date_input("Select a date to view summary", datetime.date.today(), key="summary_date")

try:
    all_meals = meals_ws.get_all_records()
    meals_df = pd.DataFrame(all_meals)
except Exception as e:
    st.error(f"Failed to fetch meals: {e}")
    meals_df = pd.DataFrame()

if meals_df.empty:
    st.info("No food entries yet.")
else:
    day_str = summary_date.strftime("%Y-%m-%d")
    df_day = meals_df[meals_df["date"] == day_str]
    if df_day.empty:
        st.info("No entries for selected date.")
    else:
        sum_cal = df_day["calories_kcal"].astype(float).sum()
        sum_prot = df_day["protein_g"].astype(float).sum()
        sum_carbs = df_day["carbs_g"].astype(float).sum()
        sum_fat = df_day["fat_g"].astype(float).sum()
        sum_fiber = df_day["fiber_g"].astype(float).sum()
        st.write(f"**Date:** {day_str}")
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Calories (kcal)", f"{sum_cal:.0f}")
        col_b.metric("Protein (g)", f"{sum_prot:.1f}")
        col_c.metric("Carbs (g)", f"{sum_carbs:.1f}")
        st.write(f"Fat: {sum_fat:.1f} g | Fiber: {sum_fiber:.1f} g")

        month_label_for_day = summary_date.strftime("%Y-%m")
        goals = goals_ws.get_all_records()
        goal_row = next((g for g in goals if g.get("month_year") == month_label_for_day), None)
        if goal_row:
            cal_goal = float(goal_row.get("calorie_goal"))
            prot_goal = float(goal_row.get("protein_goal"))
            st.write(f"**Goal for {month_label_for_day}:** {cal_goal} kcal/day, {prot_goal} g protein/day")
            cal_ok = "✅" if sum_cal <= cal_goal else "⚠️ Exceeded"
            prot_ok = "✅" if prot_goal <= sum_prot else "⚠️ Low"
            st.write(f"Calories: {cal_ok}  —  Protein: {prot_ok}")
        else:
            st.info("No goal set for this month. Set one in the left column.")

        st.dataframe(df_day.reset_index(drop=True))

# ========== DAILY NOTES ==========
st.markdown("---")
st.markdown("## ✍️ Daily Notes")
note_date = st.date_input("Note date", datetime.date.today(), key="note_date")
daily_note_text = st.text_area("Write observations, struggles, feelings about diet today", key="daily_note_text", max_chars=1000)
if st.button("💾 Save Daily Note"):
    if not daily_note_text.strip():
        st.warning("Note is empty.")
    else:
        try:
            notes_ws.append_row([note_date.strftime("%Y-%m-%d"), daily_note_text, datetime.datetime.now().isoformat()])
            st.success("Note saved.")
        except Exception as e:
            st.error(f"Failed to save note: {e}")

