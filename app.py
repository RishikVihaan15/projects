import streamlit as st
import pandas as pd
import numpy as np
import joblib
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, classification_report,
    confusion_matrix
)
from groq import Groq
import os

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(
    page_title="AI-NIDS | Advanced Student Project",
    layout="wide"
)

st.title("🛡️ AI-Based Network Intrusion Detection System")
st.caption("Random Forest + Explainable AI (Groq)")

# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------
st.sidebar.header("🔑 API Configuration")
groq_api_key = st.sidebar.text_input("Groq API Key", type="password")

st.sidebar.header("📁 Dataset")
uploaded_file = st.sidebar.file_uploader(
    "Upload CIC-IDS CSV",
    type=["csv"]
)

st.sidebar.header("🤖 Model Control")
train_btn = st.sidebar.button("🚀 Train Model")

# --------------------------------------------------
# DATA LOADING
# --------------------------------------------------
@st.cache_data
def load_data(file):
    df = pd.read_csv(file)
    df.columns = df.columns.str.strip()
    
    # Check if first row contains column names as values (duplicate header issue)
    if df.iloc[0].astype(str).str.contains('Flow Duration|Label|Fwd|Bwd').any():
        df = df.iloc[1:]  # Skip the duplicate header row
        df = df.reset_index(drop=True)
    
    # Convert numeric columns to proper types
    for col in df.columns:
        if col != 'Label':
            try:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            except:
                pass
    
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.dropna(inplace=True)
    return df

def find_matching_columns(df_columns):
    """Find matching columns in the dataset with flexible naming"""
    column_mapping = {}
    
    # Define possible variations for each feature
    feature_patterns = {
        'Flow Duration': ['Flow Duration', 'flow_duration', 'duration'],
        'Total Fwd Packets': ['Total Fwd Packets', 'Tot Fwd Pkts', 'total_fwd_packets', 'fwd_packets'],
        'Total Backward Packets': ['Total Backward Packets', 'Tot Bwd Pkts', 'total_bwd_packets', 'bwd_packets'],
        'Total Length of Fwd Packets': ['Total Length of Fwd Packets', 'TotLen Fwd Pkts', 'total_length_fwd_packets'],
        'Fwd Packet Length Max': ['Fwd Packet Length Max', 'Fwd Pkt Len Max', 'fwd_packet_length_max'],
        'Flow IAT Mean': ['Flow IAT Mean', 'Flow IAT Avg', 'flow_iat_mean'],
        'Flow IAT Std': ['Flow IAT Std', 'Flow IAT Std Dev', 'flow_iat_std'],
        'Flow Packets/s': ['Flow Packets/s', 'Flow Pkts/s', 'flow_packets_per_second']
    }
    
    for standard_name, variations in feature_patterns.items():
        for col in df_columns:
            if col in variations or any(v.lower() in col.lower() for v in variations):
                column_mapping[standard_name] = col
                break
    
    return column_mapping

FEATURES = [
    'Flow Duration',
    'Total Fwd Packets',
    'Total Backward Packets',
    'Total Length of Fwd Packets',
    'Fwd Packet Length Max',
    'Flow IAT Mean',
    'Flow IAT Std',
    'Flow Packets/s'
]

TARGET = "Label"

# --------------------------------------------------
# MODEL TRAINING
# --------------------------------------------------
def train_model(df, column_mapping):
    # Use mapped column names
    mapped_features = [column_mapping.get(f, f) for f in FEATURES if f in column_mapping]
    
    if len(mapped_features) < len(FEATURES):
        missing = [f for f in FEATURES if f not in column_mapping]
        raise ValueError(f"Missing required features: {missing}")
    
    st.write(f"📊 Using features: {mapped_features}")
    
    X = df[mapped_features].copy()
    
    st.write(f"Initial data shape: {X.shape}")
    
    # Ensure all features are numeric
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors='coerce')
    
    st.write(f"After numeric conversion: {X.shape}")
    st.write(f"NaN count per column: {X.isna().sum().to_dict()}")
    
    # Drop rows with NaN values after conversion
    X = X.dropna()
    
    st.write(f"After dropping NaN: {X.shape}")
    
    if len(X) == 0:
        raise ValueError("No valid data rows remaining after cleaning. Please check your dataset format.")
    
    # Find the Label column
    label_col = 'Label' if 'Label' in df.columns else ' Label'
    if label_col not in df.columns:
        # Try to find any column with 'label' in it
        label_cols = [col for col in df.columns if 'label' in col.lower()]
        if label_cols:
            label_col = label_cols[0]
        else:
            raise ValueError("Could not find 'Label' column in dataset")
    
    st.write(f"Using label column: '{label_col}'")
    
    y = df.loc[X.index, label_col]
    
    st.write(f"Label distribution: {y.value_counts().to_dict()}")
    
    if len(X) < 10:
        raise ValueError(f"Not enough data samples ({len(X)}). Need at least 10 rows for training.")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.25,
        random_state=42,
        stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=15,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )

    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)

    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "report": classification_report(y_test, y_pred, output_dict=True),
        "confusion": confusion_matrix(y_test, y_pred)
    }

    joblib.dump(model, "nids_model.pkl")
    joblib.dump(column_mapping, "column_mapping.pkl")
    return model, X_test, y_test, y_prob, metrics, mapped_features

# --------------------------------------------------
# MAIN APP
# --------------------------------------------------
if uploaded_file:
    df = load_data(uploaded_file)
    st.success(f"Dataset Loaded — {len(df)} packets")
    
    # Show available columns
    with st.expander("📋 Dataset Columns"):
        st.write(f"Total columns: {len(df.columns)}")
        st.write(list(df.columns))
        
        # Show first few rows
        st.write("First 3 rows:")
        st.dataframe(df.head(3))
        
        # Show data types
        st.write("Column data types:")
        st.write(df.dtypes)
    
    # Find matching columns
    column_mapping = find_matching_columns(df.columns)
    
    if len(column_mapping) < len(FEATURES):
        missing = [f for f in FEATURES if f not in column_mapping]
        st.error(f"⚠️ Missing required features: {missing}")
        st.info("Please upload a CIC-IDS dataset with the required network traffic features.")
        st.info("💡 Your dataset columns don't match the expected CIC-IDS format. You may need a different dataset.")
    else:
        st.success(f"✅ Found {len(column_mapping)} matching features")
        with st.expander("🔗 Column Mapping"):
            for standard, actual in column_mapping.items():
                st.write(f"• {standard} → {actual}")

    if train_btn:
        if len(column_mapping) < len(FEATURES):
            st.error("Cannot train: Missing required features. Please upload a proper CIC-IDS dataset.")
        else:
            with st.spinner("Training Advanced NIDS Model..."):
                try:
                    model, X_test, y_test, y_prob, metrics, mapped_features = train_model(df, column_mapping)
                    st.session_state.update({
                        "model": model,
                        "X_test": X_test,
                        "y_test": y_test,
                        "y_prob": y_prob,
                        "metrics": metrics,
                        "mapped_features": mapped_features
                    })
                    st.success("Model Training Complete!")
                except Exception as e:
                    st.error(f"Training failed: {str(e)}")
                    import traceback
                    with st.expander("🔍 Error Details"):
                        st.code(traceback.format_exc())

# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------
if "model" in st.session_state:
    st.header("📊 Threat Detection Dashboard")

    col1, col2 = st.columns(2)

    # ---- RANDOM PACKET ----
    if col1.button("🎯 Capture Live Packet"):
        idx = np.random.randint(len(st.session_state["X_test"]))
        packet = st.session_state["X_test"].iloc[idx]
        true_label = st.session_state["y_test"].iloc[idx]

        st.session_state["packet"] = packet
        st.session_state["true_label"] = true_label

    # ---- DISPLAY ----
    if "packet" in st.session_state:
        packet = st.session_state["packet"]

        col1.subheader("📦 Packet Features")
        col1.dataframe(packet)

        prediction = st.session_state["model"].predict([packet])[0]
        proba = max(st.session_state["model"].predict_proba([packet])[0])

        col2.subheader("🚨 Detection Result")

        if prediction == "BENIGN":
            col2.success("BENIGN TRAFFIC")
        else:
            col2.error(f"ATTACK DETECTED — {prediction}")

        col2.metric("Attack Confidence", f"{proba*100:.2f}%")
        col2.caption(f"Actual Label: {st.session_state['true_label']}")

        # ---- FEATURE IMPORTANCE ----
        st.subheader("🔍 Feature Contribution")
        importance = st.session_state["model"].feature_importances_
        mapped_features = st.session_state.get("mapped_features", FEATURES)
        imp_df = pd.DataFrame({
            "Feature": mapped_features,
            "Importance": importance
        }).sort_values(by="Importance", ascending=False)

        st.bar_chart(imp_df.set_index("Feature"))

        # ---- AI EXPLANATION ----
        st.subheader("🧠 AI Security Analyst (Groq)")
        if st.button("Explain Attack"):
            if not groq_api_key:
                st.warning("Enter Groq API key")
            else:
                client = Groq(api_key=groq_api_key)

                prompt = f"""
You are a SOC analyst.

Prediction: {prediction}
Confidence: {proba:.2f}

Packet Features:
{packet.to_string()}

Explain:
• Why this traffic looks {prediction}
• Which 2-3 features matter most
• Severity level (Low/Medium/High)
• One mitigation step
Use simple student-friendly language.
"""

                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5
                )

                st.info(response.choices[0].message.content)

    # ---- MODEL METRICS ----
    st.header("📈 Model Performance")

    st.metric("Accuracy", f"{st.session_state['metrics']['accuracy']*100:.2f}%")

    st.text("Classification Report")
    st.json(st.session_state["metrics"]["report"])

    st.text("Confusion Matrix")
    st.write(st.session_state["metrics"]["confusion"])

else:
    st.info("Upload dataset & train model to begin.")
