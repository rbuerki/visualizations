import numpy as np
import plotly.graph_objects as go


def create_wide_df_sankey(df, month_list, segment_col):
    """This function creates the "base df" containing all segment values."""
    assert len(month_list) == 2, "Please enter 2 months only."

    df_wide = df.pivot(
        index='MemberAK',
        columns='yearmon',
        values=[segment_col]
    )

    df_wide.columns = list(df_wide.columns.get_level_values("yearmon"))
    df_wide = df_wide[month_list]
    df_wide["count"] = 1

    df_wide = df_wide.groupby(month_list).agg({"count": "sum"}).reset_index()
    df_wide.columns = ["source", "target", "count"]

    return df_wide


def display_sankey(df, cluster_value, month_list):
    df_specific = create_specific_df_sankey(df, cluster_value)
    target_index = get_index_of_target_value(df_specific, cluster_value)
    display_sankey_specific(df_specific, cluster_value, target_index, month_list)


def create_specific_df_sankey(df, cluster_value):
    df = df.loc[df["source"] == cluster_value].copy()
    df.sort_values(["count"], ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.drop("source", axis=1, inplace=True)
    df["pct"] = df["count"] / df["count"].sum()
    return df


def get_index_of_target_value(df, cluster_value):
    return df.loc[df['target'] == cluster_value].index[0]


def display_sankey_specific(df, cluster_value, target_index, month_list):
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line={"color": "black", "width": 0.5},
            label=df["target"],
            color="lightseagreen",
            hovertemplate=(
                "<b>%{label} </b> <br>Total: %{value:.3s} <extra></extra>"
            )
        ),
        link=dict(
            source=[target_index] * len(df),
            target=np.arange(0, len(df)),
            value=df["count"],
            label=df["target"],
            # customdata=df["pct"],  -- seems to be a bug, cannot pass
            hovertemplate=(
                "<b>%{label} </b> <br>n: %{value:,.0f} <extra></extra>"
            )
        )
    )])

    fig.update_layout(
        title_text=f"<b>{cluster_value}</b>: {month_list[0]} to {month_list[1]}",
        font_size=10,
        autosize=True,
        width=800,
        height=500,
    )

    fig.show()
