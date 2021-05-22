import numpy as np
import pandas as pd
import plotly.io as pio
import plotly.graph_objects as go
import bcag
from bcag.sql_utils import execute_stored_procedure
import seaborn as sns
from matplotlib.colors import ListedColormap


def counts(
    df: pd.DataFrame, g_var: str, t_var: str, t_val: list, d_var: str
) -> pd.DataFrame:
    """count nobs grouped on source and target

    Parameters
    ----------
    df : pd.DataFrame
        dataframe 
    g_var : str
        entity
    t_var : str
        time variable
    t_val : list
        labels of time variable
    d_var : str
        dependent variable to be analyzed

    Returns
    -------
    pd.DataFrame
        aggregated dataframe
    """
    df_tmp = df.pivot(index=g_var, columns=t_var, values=d_var).fillna(
        value={
            t_val[0]: "New Customer",
            t_val[1]: "Lost Customer"
        }
    ).groupby([t_val[0],
               t_val[1]])[t_val[1]].count().rename("n_accounts").reset_index()
    df_tmp = df_tmp.rename(columns={t_val[0]: "source", t_val[1]: "target"})
    df_base_agg = (
        df_tmp.assign(
            n_total_target=df_tmp.groupby("target"
                                          )["n_accounts"].transform("sum"),
            n_total_source=df_tmp.groupby("source")
            ["n_accounts"].transform("sum")
        ).eval("prop_accounts_target = n_accounts / n_total_target").
        eval("prop_accounts_source = n_accounts / n_total_source").round(6)
    )
    cols_alluvial = ["source", "target", "n_accounts"]
    df_base_agg_alluvial = df_base_agg[cols_alluvial].copy()
    return df_base_agg, df_base_agg_alluvial


def to_treemap(
    df: pd.DataFrame, df_base_agg: pd.DataFrame, direction: list
) -> pd.DataFrame:
    """bring dataframe into format required for plotly treemap function

    Parameters
    ----------
    df : pd.DataFrame
        dataframe with columns source, target, and n_accounts. \
            source and target have to be of categorical datatype
    df_base_agg : pd.DataFrame
        with counts() aggregated dataframe
    direction : list
        list with direction, in which analysis should be shown

    Returns
    -------
    pd.DataFrame
        dataframe required for treemap function
    """
    df_help = pd.DataFrame(
        {
            direction[0]: np.repeat("", len(df[direction[0]].cat.categories)),
            direction[1]: df[direction[0]].cat.categories.astype("string"),
            "n_accounts": df.groupby(direction[0])["n_accounts"].sum()
        }
    )
    df_help[f"prop_accounts_{direction[0]}"
            ] = df_help["n_accounts"] / df_help["n_accounts"].sum()
    df = df.merge(
        df_base_agg[["source", "target", f"prop_accounts_{direction[0]}"]],
        how="left",
        on=["source", "target"]
    )
    df[direction] = df[direction].astype("string")
    df[direction[1]] = df[direction[0]] + " - " + df[direction[1]]
    df_tree = pd.concat(
        [
            df[[
                direction[0], direction[1], "n_accounts",
                f"prop_accounts_{direction[0]}"
            ]], df_help
        ]
    )
    return df_tree


def treemap(df: pd.DataFrame, direction: list) -> go.Figure:
    """return treemap plot in selected direction

    Parameters
    ----------
    df : pd.DataFrame
        dataframe prepared for treemap function
    direction : list
        list with direction, in which analysis should be shown

    Returns
    -------
    go.Figure
        treemap, which is instance of plotly.graph_objects.Figure
    """
    f = go.Figure(
        go.Treemap(
            labels=df[direction[1]],
            parents=df[direction[0]],
            values=df["n_accounts"],
            branchvalues="total",
            textinfo="label+value+percent parent+percent entry",
            marker=dict(
                colors=df[f'prop_accounts_{direction[0]}'],
                colorscale='viridis'
            ),
            hovertemplate=(
                '<b>%{label} </b> <br> Nr. Accounts: %{value}<br> Prop. Accounts: %{color:.1%}'
            ),
        ), {
            "height": 800,
            "width": 800
        }
    )
    return f


def to_alluvial(df: pd.DataFrame, t_val: list, direction: str) -> tuple:
    """bring df into alluvial format

    Parameters
    ----------
    df : pd.DataFrame
        dataframe in required alluvial format
    t_val : list
        time values
    direction : str
        list with direction, in which analysis should be shown

    Returns
    -------
    tuple
        df_alluvial: pd.DataFrame
            dataframe required to plot alluvial
        df: pd.DataFrame
            dataframe required for labels
    """
    l_df_lookup, l_dtypes = unique_labels(df)
    df["source"] = df["source"].astype(l_dtypes[0])
    df["target"] = df["target"].astype(l_dtypes[1])
    df_alluvial = alluvial_info(df, l_df_lookup)
    df_colors = alluvial_colors(df_alluvial, direction)
    df_alluvial = plotly_labels(df_alluvial, df_colors, direction)
    return df_alluvial, df


def unique_labels(df: pd.DataFrame) -> tuple:
    """create lookup dfs mapping category values to category labels. \,
    turn source and target variable into categories

    Parameters
    ----------
    df : pd.DataFrame
        raw dataframe

    Returns
    -------
    tuple
        l_df_lookup
            list of lookup dataframes
        l_dtypes
            list containing categorical datatypes for source and target
    """
    vals = pd.Series(np.union1d(df["source"].unique(), df["target"].unique()))
    vals = list(vals[~vals.isin(["New Customer", "Lost Customer"])])
    df_lookup_source = pd.DataFrame(
        {
            "labels": vals + ["New Customer"],
            "values": np.arange(0, (len(vals) + 1))
        }
    )
    label_dtype_source = pd.api.types.CategoricalDtype(
        categories=vals + ["New Customer"], ordered=True
    )
    df_lookup_source["labels"] = df_lookup_source["labels"].astype(
        label_dtype_source
    )

    df_lookup_target = pd.DataFrame(
        {
            "labels": vals + ["Lost Customer"],
            "values": np.arange(0, (len(vals) + 1))
        }
    )
    label_dtype_target = pd.api.types.CategoricalDtype(
        categories=vals + ["Lost Customer"], ordered=True
    )
    df_lookup_target["labels"] = df_lookup_target["labels"].astype(
        label_dtype_target
    )
    l_df_lookup = [df_lookup_source, df_lookup_target]
    l_dtypes = [label_dtype_source, label_dtype_target]

    return l_df_lookup, l_dtypes


def alluvial_info(df: pd.DataFrame, l_df_lookup: list) -> pd.DataFrame:
    """aggregate df returning info required for alluvial plot

    Parameters
    ----------
    df : pd.DataFrame
        raw dataframe containing all data
    l_df_lookup : list
        list with lookup dataframes for source and target

    Returns
    -------
    pd.DataFrame
        dataframe with all information required for alluvial plot
    """
    df_alluvial = (
        df.merge(
            l_df_lookup[0], how="inner", left_on="source", right_on="labels"
        ).drop(columns=["source", "labels"]
               ).rename(columns={
                   "values": "source"
               }).merge(
                   l_df_lookup[1],
                   how="inner",
                   left_on="target",
                   right_on="labels"
               ).drop(columns=["target", "labels"]
                      ).rename(columns={"values": "target"})
    )
    df_alluvial["target"] = df_alluvial["target"] + df_alluvial["source"].max(
    ) + 1
    (df_alluvial.rename(columns={"n_accounts": "value"}, inplace=True))
    return df_alluvial


def alluvial_colors(df: pd.DataFrame, direction: str) -> pd.DataFrame:
    """create a df containing required discrete colors

    Parameters
    ----------
    df : pd.DataFrame
        dataframe, which is going to be used for alluvial plot
    direction : str
        direction, in which analysis should be shown

    Returns
    -------
    pd.DataFrame
        dataframe mapping values to colors
    """
    plotly_template = pio.templates["plotly"]
    colors = plotly_template["layout"]["colorway"]
    vals = sorted(df[direction].unique())
    df_colors = pd.DataFrame({direction: vals, "color": colors[0:len(vals)]})
    return df_colors


def plotly_labels(
    df_alluvial: pd.DataFrame, df_colors: pd.DataFrame, direction: str
) -> pd.DataFrame:
    """add labels to be shown in the plot

    Parameters
    ----------
    df_alluvial : pd.DataFrame
        dataframe in format required for alluvial plot
    df_colors : pd.DataFrame
        dataframe mapping colors to values
    direction : str
        direction, in which analysis should be shown

    Returns
    -------
    pd.DataFrame
        dataframe with all labels formatted with regards to plotly object
    """
    df_alluvial = df_alluvial.sort_values(["source", "target"])
    df_alluvial = (df_alluvial.merge(df_colors, how="inner", on=direction))
    df_alluvial = df_alluvial.assign(
        label=np.round(
            df_alluvial["value"] /
            df_alluvial.groupby(direction)["value"].transform("sum"), 2
        )
    )
    return df_alluvial


def alluvial(
    df_base_agg_alluvial: pd.DataFrame, df_alluvial: pd.DataFrame
) -> go.Figure:
    """plot alluvial from source to target in reading direction

    Parameters
    ----------
    df_base_agg_alluvial : pd.DataFrame
        dataframe with labels as categories
    df_alluvial : pd.DataFrame
        main dataframe for plot

    Returns
    -------
    go.Figure
        plotly.graph_object
    """
    cat_source = [
        c for c in df_base_agg_alluvial["source"].cat.categories
        if c != "Lost Customer"
    ]
    cat_target = [
        c for c in df_base_agg_alluvial["target"].cat.categories
        if c != "New Customer"
    ]
    f = go.Figure(
        data=[
            go.Sankey(
                node=dict(
                    pad=15,
                    thickness=20,
                    line=dict(color="black", width=0.5),
                    label=cat_source + cat_target,
                    color=list(np.tile(df_alluvial["color"].unique(), 2))
                ),
                link=df_alluvial.to_dict("list")
            )
        ],
        layout={
            "height": 800,
            "width": 800
        }
    )
    f.update_layout(title_text="Development Path", font_size=10)
    return f


def shown_columns() -> dict:
    """what columns should be shown in the overview tables?

    Returns
    -------
    dict
        dictionary mapping ugly column names to formatted column names
    """
    columns = {
        "source": "Source",
        "target": "Target",
        "n_accounts": "Nr. Accounts",
        "n_total_source": "Nr. Accounts Source",
        "prop_accounts_source": "Proportion Accounts Source"
    }
    return columns


def sort_transitions(df: pd.DataFrame, is_transition: bool) -> None:
    """sort according to proportion of transition

    Parameters
    ----------
    df : pd.DataFrame
        dataframe with required columns
    is_transition : bool
        stability (proportion of entities staying in category) or transitions \,
        (proportion of entities swapping around)

    Returns
    -------
    None
    """
    columns = shown_columns()
    if is_transition:
        title = "Transitions of Categories"
    else:
        title = "Stability of Categories"
    if is_transition:
        sign = "!"
    else:
        sign = "="
    df_transition = (
        df[[
            "source", "target", "n_accounts", "n_total_source",
            "prop_accounts_source"
        ]].copy()
    )
    df_transition["prop_accounts_source"] = df_transition["prop_accounts_source"
                                                          ].round(4)
    df_out = (
        df_transition.query(f"source {sign}= target").sort_values(
            "prop_accounts_source", ascending=False
        ).reset_index(drop=True
                      ).rename(columns=columns
                               ).head(20).style.background_gradient(
                                   subset=["Proportion Accounts Source"],
                                   cmap="viridis"
                               ).bar(subset=["Nr. Accounts"]
                                     ).set_caption(title).format(
                                         {
                                             "Nr. Accounts": "{:,.0f}",
                                             "Nr. Accounts Source": "{:,.0f}",
                                             "Proportion Accounts Source":
                                             "{:.2%}"
                                         }
                                     )
    )
    return df_out


def demographic_addons(df: pd.DataFrame, jamo: int) -> pd.DataFrame:
    """read addon data from jemas and join with df

    Parameters
    ----------
    df : pd.DataFrame
        data frame with konto_lauf_id as column

    Returns
    -------
    pd.DataFrame
        joined df
    """
    sp_args = dict({"jamo_last": jamo})
    engine_jemas = bcag.connect("jemas", "prod", "jemas_temp")
    execute_stored_procedure(
        engine_jemas, "thm.addons_purchase_interest", sp_args
    )
    df_addons = pd.read_sql(
        "select * from jemas_temp.thm.purchase_interest_addons", engine_jemas
    )
    df_rich = df.merge(df_addons, how="inner", on="konto_lauf_id")
    return df_rich


def prepare_demographic_addons(
    df_base: pd.DataFrame, jamo: int, d_var: str
) -> tuple:
    """add demographics queried from jemas

    Parameters
    ----------
    df_base : pd.DataFrame
        dataframe with konto_lauf_id and d_var (category: cluster, segment, ...) in columns
    jamo : int
        jamo to query data from
    d_var : str
        category: cluster, segment, ...

    Returns
    -------
    tuple
        df with added info and aggregated df to plot heatmap
    """
    df_rich = demographic_addons(df_base.query(f"""jamo == {jamo}"""), jamo)
    df_rich.drop(columns=["konto_id", "jamo"], inplace=True)
    df_rich["prop_w"] = df_rich["anredecode"] == "W"
    df_rich["prop_cc"] = df_rich["cardprofile"] == "CC"
    df_counts = pd.DataFrame(df_rich[d_var].value_counts()).reset_index()
    df_counts.rename(
        columns={
            "index": d_var,
            d_var: "Nr. Accounts"
        }, inplace=True
    )
    df_rich.columns = [
        "konto_lauf_id",
        d_var,
        "Tenure (Yrs)",
        "Age (Yrs)",
        "Anredecode",
        "Cardprofile",
        "Turnover (12 Mth)",
        "CM1 (12 Mth)",
        "Payment Type",
        "Financial Profile",
        "Credit RS YR",
        "Revenue Annual Fee (12 Mth)",
        "Revenue Interest (12 Mth)",
        "Prop Women",
        "Prop CC",
    ]
    return df_rich, df_counts


def heatmap_cols_z(df, df_counts, d_var, cols, fmt, ax, **kwargs):
    if cols == "all":
        cols = [col for col in df.columns.values]
    df_agg = df[cols].groupby(d_var).mean().reset_index()
    df_agg[d_var] = df_agg[d_var].astype("category")
    df_agg[d_var] = df_agg[d_var].cat.set_categories(
        list(df_counts[d_var].values), ordered=True
    )
    df_agg.sort_values(d_var, inplace=True)
    df_agg = df_agg.merge(df_counts, how="inner", on=d_var)
    df_agg.set_index(d_var, inplace=True)
    if df_agg.shape[0] > 1:
        df_agg_z = df_agg.apply(lambda x: (x - x.mean()) / x.std())
        sns.heatmap(df_agg_z, annot=df_agg, fmt=fmt, cmap="viridis", ax=ax)
        ax.set_title(kwargs["title"])
    else:
        df_agg.drop(columns="Nr. Accounts", inplace=True)
        if kwargs["no_color"] is True:
            sns.heatmap(
                df_agg,
                annot=True,
                fmt=fmt,
                cmap=ListedColormap(["#B0D1F7"]),
                ax=ax
            )
        else:
            sns.heatmap(df_agg, annot=True, fmt=fmt, cmap="viridis", ax=ax)
