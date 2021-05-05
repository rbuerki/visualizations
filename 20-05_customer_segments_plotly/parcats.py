import plotly.graph_objects as go

from utils import rfm_color_map, cls_color_map, aff_color_map

rfm_col = "RFM_Segment"
rfm_title = "RFM-Segments"

cls_col = "Lifecycle_Segment"
cls_title = "Customer Lifetime Stages"

aff_col = "Affinität_Segment"
aff_title = "Affinities Clusters"

rfm_args = [rfm_col, rfm_title, rfm_color_map]
cls_args = [cls_col, cls_title, cls_color_map]
aff_args = [aff_col, aff_title, aff_color_map]


def display_parcat(df, month_list, segment_col, title, color_map):
    df_wide = create_wide_df(df, month_list, segment_col, color_map)
    display_parcats_over_time(df_wide, month_list, title, color_map)


def create_wide_df(df, month_list, segment_col, color_map):
    df_wide = df.pivot(
        index='MemberAK',
        columns='yearmon',
        values=["RFM_Segment", "Affinität_Segment", "Lifecycle_Segment"]
    )

    df_wide = df_wide[[segment_col]].copy()
    df_wide.columns = list(df_wide.columns.get_level_values("yearmon"))
    # Make sure the columns are arranged in the right order
    df_wide = df_wide.reindex(columns=month_list)
    df_wide["color"] = df_wide.iloc[:, -1].apply(lambda x: color_map.get(x, "#e5e6eb"))
    return df_wide


def display_parcats_over_time(df, month_list, title, color_map):

    assert len(month_list) in (2, 3), "Set `n_months` to 2 or 3, please."

    m1_dim = go.parcats.Dimension(
        values=df[month_list[0]],
        categoryorder="array",
        categoryarray=list(color_map.keys()),
        label=month_list[0]
    )

    m2_dim = go.parcats.Dimension(
        values=df[month_list[1]],
        categoryorder="array",
        categoryarray=list(color_map.keys()),
        label=month_list[1]
    )

    if len(month_list) == 3:
        m3_dim = go.parcats.Dimension(
            values=df[month_list[2]],
            categoryorder="array",
            categoryarray=list(color_map.keys()),
            label=month_list[2]
        )

        dimensions = [m1_dim, m2_dim, m3_dim]
    else:
        dimensions = [m1_dim, m2_dim]

    fig = go.Figure(
        data=[
            go.Parcats(
                dimensions=dimensions,
                line={'color': df["color"]}
            )
        ]
    )

    fig.update_layout(title_text=f"<b>{title}<br />")

    fig.show()
