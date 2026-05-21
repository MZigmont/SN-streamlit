import pandas as pd
import streamlit as st


def display(validation_dict):
    for label, value in validation_dict.items():
        if isinstance(value, pd.DataFrame):
            if len(value) > 0:
                st.error(f"{label}: {len(value)} issue(s) found")
                st.dataframe(value)
            else:
                st.success(f"{label}: OK")
            continue

        if value:
            st.error(f"{label}: {value}")
        else:
            st.success(f"{label}: OK")