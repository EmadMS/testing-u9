from flask import Flask, render_template, jsonify, request, send_file
import pandas as pd
import numpy as np
from scipy import stats
import os
import io

app = Flask(__name__)
DATA_FILE = "static/footfall_data.csv"

# ==========================================
# PAGE COMPONENT ROUTES
# ==========================================
@app.route('/')
def index(): return render_template('index.html')

@app.route('/dashboard')
def dashboard(): return render_template('dashboard.html')

@app.route('/zones')
def zones(): return render_template('zones.html')

@app.route('/statistics')
def statistics(): return render_template('statistics.html')

@app.route('/export')
def export(): return render_template('export.html')

@app.route('/gdpr')
def gdpr(): return render_template('gdpr.html')

# ==========================================
# API: DASHBOARD & ZONES
# ==========================================
@app.route('/api/data')
def get_data():
    try:
        df = pd.read_csv(DATA_FILE)
        if df.empty: return jsonify({"status": "empty"})
        
        stats_data = {
            "total_footfall": len(df),
            "avg_dwell_min": round(df["DwellTime_s"].mean() / 60, 1),
            "avg_engagement": round(df["EngagementScore"].mean(), 1),
            "ai_confidence": round(df["AI_Confidence"].mean() * 100, 1)
        }

        zone_metrics = {}
        for zone, group in df.groupby("Zone"):
            zone_metrics[zone] = {
                "footfall": len(group),
                "dwell_min": round(group["DwellTime_s"].mean() / 60, 1),
                "engagement": round(group["EngagementScore"].mean(), 1),
                "conversion": round(min(95, group["EngagementScore"].mean() * 1.1), 1) 
            }
        
        stats_data["zones"] = zone_metrics
        return jsonify({"status": "success", "data": stats_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# ==========================================
# API: UNIT 10 STATISTICAL MATH
# ==========================================
@app.route('/api/unit10')
def get_unit10_stats():
    try:
        df = pd.read_csv(DATA_FILE)
        dwell = df['DwellTime_s']
        
        # Routine
        mean, median, mode, std = dwell.mean(), dwell.median(), dwell.mode()[0], dwell.std()
        
        # Non-Routine
        trimmed = stats.trim_mean(dwell, 0.1)
        Q1, Q3 = dwell.quantile([0.25, 0.75])
        weighted_mean = np.average(dwell, weights=df['AI_Confidence'])
        
        # Hypothesis Testing (T-Test)
        ent = df[df['Zone'] == 'Entrance']['DwellTime_s']
        chk = df[df['Zone'] == 'Checkout']['DwellTime_s']
        t_stat, p_val = stats.ttest_ind(ent, chk, equal_var=False) if len(ent)>1 and len(chk)>1 else (0,1)

        # Regression
        lin_slope, lin_int, lin_r, _, _ = stats.linregress(df['DwellTime_s'], df['EngagementScore'])
        valid_data = df[(df['DwellTime_s'] > 0) & (df['EngagementScore'] > 0)]
        power_b, log_a, power_r, _, _ = stats.linregress(np.log(valid_data['DwellTime_s']), np.log(valid_data['EngagementScore']))

        return jsonify({
            "status": "success",
            "routine": {"mean": round(mean, 1), "median": round(median, 1), "mode": round(mode, 1), "std": round(std, 1), "range": round(dwell.max()-dwell.min(), 1)},
            "non_routine": {"trimmed": round(trimmed, 1), "weighted": round(weighted_mean, 1), "iqr": round(Q3 - Q1, 1)},
            "ttest": {"t_stat": round(t_stat, 2), "p_val": round(p_val, 4)},
            "regression": {
                "linear": {"slope": round(lin_slope, 2), "int": round(lin_int, 2), "r2": round(lin_r**2, 4)},
                "power": {"a": round(np.exp(log_a), 2), "b": round(power_b, 2), "r2": round(power_r**2, 4)}
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# ==========================================
# REPORT EXPORT API (FIXED)
# ==========================================
from flask import Response # Add this import at the top of app.py if missing

@app.route('/api/export')
def export_data():
    try:
        format_type = request.args.get('format', 'csv')
        df = pd.read_csv(DATA_FILE)
        
        # Clean data for GDPR compliance before export
        if 'DetectionID' in df.columns:
            df['DetectionID'] = df['DetectionID'].apply(lambda x: f"ANON-HASH-{str(x)[-6:]}")

        if format_type == 'xlsx':
            output = io.BytesIO()
            # Requires pip install openpyxl
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Footfall Analytics')
            output.seek(0)
            return send_file(
                output, 
                download_name='Footfall_Analytics_Export.xlsx', 
                as_attachment=True, 
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            
        elif format_type == 'csv':
            # Bulletproof CSV export using Flask Response
            return Response(
                df.to_csv(index=False),
                mimetype="text/csv",
                headers={"Content-disposition": "attachment; filename=static/Footfall_Analytics_Export.csv"}
            )
            
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to generate {format_type.upper()}: " + str(e)})

if __name__ == "__main__":
    app.run(debug=True, threaded=True)