import streamlit as st

def display(validation_dict):

    if validation_dict['no_dupes_rowcount'] > 0:
        st.error(f"In temp_donations : this many transactions are duplicated: {validation_dict['no_dupes_rowcount']}")
    else:
        st.success("In temp_donations : all transactions were unique")
    
    if validation_dict['no_dupes_rowcount_raw'] > 0:
        st.error(f"In the raw data : this many transactions are duplicated: {validation_dict['no_dupes_rowcount_raw']}")
    else:
        st.success("In the raw data : all transactions were unique")

    if len(validation_dict['unaccounted_trans_df']) > 0:
        st.error(f"In the raw data, these records weren't accounted for: ")
        st.dataframe(validation_dict['unaccounted_trans_df'])
    else:
        st.success("In the raw data : all transactions were accounted for")

    if len(validation_dict['no_dupes_donations_df']) > 0:
        st.error(f"In donations, these transactions have same trans ID and source: ")
        st.dataframe(validation_dict['no_dupes_donations_df'])
    else:
        st.success("In donations: all trans IDs are unique to their source")

    if len(validation_dict['no_dupes_temp_donors_df']) > 0:
        st.error("In temp_donors, donors have same first and last name: ")
        st.dataframe(validation_dict['no_dupes_temp_donors_df'])
    else:
        st.success("In temp_donors: all donors have unique first and last names")
    
    if len(validation_dict['no_dupes_donors_df']) > 0:
        st.error("In donors, these donors have same donor reporting names: ")
        st.dataframe(validation_dict['no_dupes_donors_df'])
    else:
        st.success("In donors: all donors have unique donor reporting names")

    if len(validation_dict['no_dupes_temp_aliases_df']) > 0:
        st.error("In temp_aliases, these aliases have identical fields: ")
        st.dataframe(validation_dict['no_dupes_temp_aliases_df'])
    else:
        st.success("In temp_aliases: all aliases are unique")
    
    if len(validation_dict['no_dupes_aliases_df']) > 0:
        st.error("In aliases, these aliases have identical fields: ")
        st.dataframe(validation_dict['no_dupes_aliases_df'])
    else:
        st.success("In aliases: all aliases are unique")