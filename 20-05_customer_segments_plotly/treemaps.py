import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils import rfm_color_map, cls_color_map, aff_color_map


rfm_levels = ["RFM_Segment", "yearmon"]
rfm_title = "RFM-Segments"

cls_levels = ["Lifecycle_Segment", "yearmon"]
cls_title = "Customer Lifetime Stages"

aff_levels = ["Affinität_Segment", "yearmon"]
aff_title = "Affinities Clusters"

value_col = "monetary"
count_col = "count"


rfm_args = [rfm_levels, rfm_title, value_col, count_col, rfm_color_map]
cls_args = [cls_levels, cls_title, value_col, count_col, cls_color_map]
aff_args = [aff_levels, aff_title, value_col, count_col, aff_color_map]


def display_treemaps(df, levels, title, value_column, count_column, color_map):
    df_hier = create_hierarchical_df(
        df, levels, value_column, count_column, color_map
    )
    display_treemap_by_value_count(df_hier, title)


def create_hierarchical_df(
    df, levels, value_column, count_column=None, color_map=None
):
    """
    Build a hierarchy of levels for Sunburst or Treemap charts.
    Levels are given starting from the bottom to the top of the hierarchy,
    ie the last level corresponds to the root.
    """
    df_hierarchical = pd.DataFrame(
        columns=["id", "parent", "label", "value", "count", "color"]
    )

    for i, level in enumerate(levels):
        df_grouped = df.groupby(levels[i:]).sum().reset_index()
        df_tree = pd.DataFrame(columns=list(df_hierarchical.columns))
        df_tree["label"] = df_grouped[level].copy()
        if i < len(levels) - 1:
            df_tree["parent"] = df_grouped[levels[i + 1]].copy()
            df_tree["id"] = (
                df_tree["label"].astype(str)
                + "/"
                + df_tree["parent"].astype(str)
            )
        else:
            df_tree["parent"] = "total"
            df_tree["id"] = df_tree["label"].astype(str)

        df_tree["value"] = df_grouped[value_column]
        if count_column is not None:
            df_tree["count"] = df_grouped[count_column]
        if color_map is not None:
            df_tree["color"] = df_tree["label"].apply(
                lambda x: color_map.get(x, "#e5e6eb")
            )

        df_hierarchical = df_hierarchical.append(df_tree, ignore_index=True)

    total = {
        "id": "total",
        "parent": "",
        "label": "total",
        "value": df[value_column].sum(),
        "count": df[count_column].sum(),
        "color": "#ffffff",
    }

    df_hierarchical = df_hierarchical.append(total, ignore_index=True)
    return df_hierarchical


def display_treemap_by_value_count(df, title):

    fig = make_subplots(
        rows=2,
        row_heights=[1, 1],
        vertical_spacing=0.1,
        subplot_titles=(
            f"{title}: <b>By Value<br />",
            f"{title}: <b>By Members<br />",
        ),
        specs=[[{"type": "domain"}], [{"type": "domain"}]],
    )

    fig.add_trace(
        go.Treemap(
            labels=df["label"],
            ids=df["id"],
            parents=df["parent"],
            values=df["value"],
            branchvalues="total",
            marker=dict(colors=df["color"],),
            texttemplate=(
                "<b>%{label} </b> <br>Value: %{value:.3s} <br>%{percentParent:.1%}"
            ),
            hovertemplate=(
                "<b>%{label} </b> <br>Value: %{value:,.0f} <br>%{percentParent:.1%}"
            ),
            name="",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Treemap(
            labels=df["label"],
            ids=df["id"],
            parents=df["parent"],
            values=df["count"],
            branchvalues="total",
            marker=dict(colors=df["color"],),
            texttemplate=(
                "<b>%{label} </b> <br>Value: %{value:n} <br>%{percentParent:.1%}"
            ),
            hovertemplate=(
                "<b>%{label} </b> <br>Value: %{value:n} <br>%{percentParent:.1%}"
            ),
            name="",
        ),
        row=2,
        col=1,
    )

    fig.update_layout(height=1000,)

    fig.show()
