import pandas as pd
from sqlalchemy import create_engine


rfm_color_map = {
    "Prized Champs": "#004c4c",
    "High-Spenders": "#66b2b2",
    "Loyals": "#008080",
    "Low-Spenders": "#66b2b2",
    "Hesitants": "#b2d8d8",
    "Sleepers": "#a7adba",
    "Lost Inactives": "#c0c5ce",
}

cls_color_map = {
    "New Customer": "#004c4c",
    "Regularly Active": "#008080",
    "Leaving Customer": "#b2d8d8",
    "Sleepers": "#a7adba",
    "Lost Inactives": "#c0c5ce",
}

aff_color_map = {
    "Fashionistas": "#004c4c",
    "Gentlemen": "#66b2b2",
    "Mixed Fashion": "#008080",
    "The Casuals": "#66b2b2",
    "Cozy Home": "#b2d8d8",
    "Missing SAP": "#a7adba",
    "None": "#c0c5ce",
}


def get_segments_data(yearmon_dict):
    _, connection = connect_to_db()
    query = complete_query(yearmon_dict)
    print("Fetching data ...\n")
    data = fetch_data(connection, query)
    print("Preparing dataframe ...\n")
    df = prepare_dataframe(data, yearmon_dict)
    print("Done!")
    return df


def connect_to_db():
    """Return engine and connection to DB on B2B2C server."""
    con_str = "mssql+pyodbc://@agtst01/xxx_analytics?driver=ODBC Driver 13 for SQL Server"
    engine = create_engine(con_str, fast_executemany=True)
    connection = engine.connect()
    return engine, connection


def complete_query(yearmon_dict):
    query = f"""
        SELECT
            yearmon,
            MemberAK,
            RFM_Segment,
            Lifecycle_Segment,
            Affinität_Segment,
            monetary
        FROM xxx_analytics.dbo.xxx_segments_hist
        WHERE yearmon in ({", ".join(str(x) for x in list(yearmon_dict.keys()))})
        """
    return query


def fetch_data(connection, query):
    return connection.execute(query).fetchall()


def prepare_dataframe(data, yearmon_dict):
    df = pd.DataFrame(data, columns=data[0].keys())

    # Redefine datatypes were necessary
    df = df.astype({"monetary": float, "MemberAK": str,})

    # Rename some variables (for improved readability)
    df["yearmon"] = df["yearmon"].map(yearmon_dict)
    df["Affinität_Segment"] = df["Affinität_Segment"].str.replace(
        "Missing SAP Product Categories", "Missing SAP"
    )
    df["Lifecycle_Segment"] = df["Lifecycle_Segment"].str.replace(
        "Regularly Active Customer", "Regularly Active"
    )

    # Fill in a string for the missing affinites segments
    df["Affinität_Segment"].fillna("None", inplace=True)

    # Add a count column for the treemap plots
    df["count"] = 1

    return df
