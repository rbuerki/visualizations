import bcag
from bcag.sql_utils import execute_stored_procedure
import numpy as np
import pandas as pd
from datetime import datetime
from functools import reduce
from matplotlib import pyplot as plt
import seaborn as sns


def load_survival_data(sp_params: dict) -> pd.DataFrame:
    """load survival data from jemas and return them as df

    Parameters
    ----------
    sp_params : dict
        defining start and end of considered period
        containing sql string to create groups

    Returns
    -------
    pd.DataFrame
        df with required data
    """
    engine = bcag.connect("jemas", "prod", "jemas_temp")
    execute_stored_procedure(engine, "thm.sp_survival_default", sp_params)
    df_ncas = pd.read_sql("select * from thm.survival_default", engine)
    return df_ncas


def preprocess_df(df_ncas: pd.DataFrame) -> pd.DataFrame:
    """preprocess df and return clean df

    Parameters
    ----------
    df_ncas : pd.DataFrame
        loaded df from jemas

    Returns
    -------
    pd.DataFrame
        cleaned df
    """
    df_ncas, idx = clean_status(df_ncas)
    df_ncas = manipulate_dates(df_ncas)
    return df_ncas, idx


def clean_status(df_ncas: pd.DataFrame) -> tuple:
    """convert status to categorical dtype

    Parameters
    ----------
    df_ncas : pd.DataFrame
        nca df

    Returns
    -------
    tuple
        pd.DataFrame: nca df with status as category
        tuple: idxs with used status
    """
    # order status category

    possible_status = [
        "Approved CCF", "Approved CCL", "Fallback CCL", "Approved PP",
        "Fallback PP", "Rejected CCF", "Rejected CCL"
    ]
    actual_status = list(df_ncas["status_full"].unique())
    idx = [s in actual_status for s in possible_status]
    status = np.array(possible_status)[idx].tolist()
    df_ncas["status_full"] = df_ncas["status_full"].astype("category")
    df_ncas["status_full"] = (
        df_ncas["status_full"].cat.reorder_categories(status, ordered=True)
    )
    return df_ncas, idx


def manipulate_dates(df_ncas: pd.DataFrame) -> pd.DataFrame:
    """convert date columns to date dtype and add cohort by year

    Parameters
    ----------
    df_ncas : pd.DataFrame
        nca df

    Returns
    -------
    pd.DataFrame
        nca df with date columns as date dtype and cohort column
    """
    df_ncas["bearbeitet_datum"] = (
        pd.to_datetime(df_ncas["bearbeitet_datum"], format="%Y-%m-%d")
    )
    df_ncas["cohort"] = df_ncas["bearbeitet_datum"].dt.year
    return df_ncas


def proportion_by_status(df_ncas: pd.DataFrame) -> tuple:
    """aggregate data by cohort, group, and status

    Parameters
    ----------
    df_ncas : pd.DataFrame
        nca df

    Returns
    -------
    tuple
        pd.DataFrame: aggregated df
        list: distinct cohorts
    """
    df_status = df_ncas.query("month_nr == 1").copy()
    df_tmp = (
        df_status.groupby(["group_name", "cohort"]
                          )["status_full"].count().reset_index().rename(
                              columns={"status_full": "n_accounts_tot"}
                          )
    )
    df_status_agg = (
        df_status.groupby(
            ["group_name", "cohort"]
        )["status_full"].value_counts().rename("n_accounts").reset_index()
    )
    df_status_agg = (
        df_status_agg.merge(df_tmp, how="inner", on=[
            "group_name", "cohort"
        ]).eval("prop_accounts = n_accounts / n_accounts_tot")
    )
    df_status_agg.sort_values(
        ["cohort", "group_name", "status_full"], inplace=True
    )
    df_status_agg["prop_accounts_cum"] = (
        df_status_agg.groupby(["group_name", "cohort"]
                              )["prop_accounts"].cumsum().shift(1).fillna(0)
    )
    df_status_agg.loc[df_status_agg["prop_accounts_cum"] == 1,
                      "prop_accounts_cum"] = 0
    cohorts = df_status_agg["cohort"].unique().tolist()
    return (df_status_agg, cohorts)


def plot_status_by_group(
    df_status_agg: pd.DataFrame, cohorts: list, status_colors: list, axs
):
    """plot distribution of status by group for different cohorts

    Parameters
    ----------
    df_status_agg : pd.DataFrame
        aggregated df
    cohorts : list
        list with cohorts to plot
    status_colors : list
        colors to be used for different status
    axs : matplotlib axes object
    """

    for i, ax in enumerate(axs.flat):
        df_tmp = df_status_agg.query(f"""cohort == {cohorts[i]}""")
        df_tmp = prop_approved(df_tmp)
        df_tmp.sort_values(["prop_ccf"], ascending=False, inplace=True)
        for idx, c in enumerate(df_tmp["status_full"].cat.categories):
            color = status_colors[idx]
            df_plt = df_tmp.query(f"""status_full == '{c}'""")
            if idx == 0:
                ax.bar("group_name", "prop_accounts", data=df_plt, color=color)
            elif idx > 0:
                ax.bar(
                    "group_name",
                    "prop_accounts",
                    data=df_plt,
                    bottom="prop_accounts_cum",
                    color=color,
                    edgecolor="white"
                )
        xlabels = list(df_tmp["group_name"].unique())
        ax.set_xticks(xlabels)
        ax.set_xticklabels(xlabels, rotation=90)
        ax.set_title(f"Cohort = {cohorts[i]}")
        if i == len(axs) - 1:
            ax.legend(df_tmp["status_full"].cat.categories, loc="right")
    return axs


def prop_approved(df_tmp: pd.DataFrame) -> pd.DataFrame:
    """add a column with the percentage approved ccf

    Parameters
    ----------
    df_tmp : pd.DataFrame
        df with columns group_name, status_full, and prop_accounts

    Returns
    -------
    pd.DataFrame
        same df with added column
    """
    df_max = (
        df_tmp.query("status_full == 'Approved CCF'")[[
            "group_name", "prop_accounts"
        ]].rename(columns={"prop_accounts": "prop_ccf"})
    )
    df_tmp = df_tmp.merge(df_max, how="inner", on="group_name")
    return df_tmp


def create_df_survival(df_ncas: pd.DataFrame, n_min: int) -> pd.DataFrame:
    """create survival df containing entries for every day since nca for
    every group, every cohort, and every status
    remove entries for groups with fewer than n_min accounts 

    Parameters
    ----------
    df_ncas : pd.DataFrame
        df with validitiy per konto_id and jamo
    n_min : int
        thx of n accounts below which groups are silently dropped

    Returns
    -------
    pd.DataFrame
        aggregated df with one columns per group, cohort, status, and days since nca
    """
    df_survival = df_ncas.query("month_nr == 1 and is_valid == 1")
    # censoring
    max_days = (
        datetime.now() - df_survival.groupby("cohort")["bearbeitet_datum"].max()
    ).dt.days.reset_index().rename(columns={"bearbeitet_datum": "max_n_days"})
    df_survival_agg = (
        df_survival.groupby(
            ["group_name", "cohort", "status_full"]
        )["n_days_to_invalid"].value_counts().rename("n_accounts").reset_index()
    )
    df_design = cross_vars(df_survival_agg, int(max_days["max_n_days"].max()))
    df_survival_agg = df_design.merge(
        df_survival_agg,
        how="left",
        on=["n_days_to_invalid", "group_name", "cohort", "status_full"]
    )
    df_survival_agg["n_accounts"].fillna(0, inplace=True)
    df_tmp = (
        df_survival.groupby(
            ["group_name", "cohort", "status_full"]
        )["konto_id"].count().rename("n_accounts_tot").reset_index()
    )
    df_survival_agg = (
        df_survival_agg.merge(
            df_tmp, how="inner", on=["group_name", "cohort", "status_full"]
        )
    )
    df_survival_agg = df_survival_agg.merge(max_days, how="inner", on="cohort")
    df_survival_agg.query("n_days_to_invalid <= max_n_days", inplace=True)
    df_survival_agg["prop_dropout"] = (
        df_survival_agg.eval("n_accounts / n_accounts_tot")
    )
    df_survival_agg["n_dropout_cum"] = df_survival_agg.groupby(
        ["group_name", "cohort", "status_full"]
    )["n_accounts"].cumsum()
    df_survival_agg["prop_survive"] = 1 - df_survival_agg.groupby(
        ["group_name", "cohort", "status_full"]
    )["prop_dropout"].cumsum()
    df_survival_agg.query(f"n_accounts_tot > {n_min}", inplace=True)
    return df_survival_agg


def cross_vars(df_survival_agg: pd.DataFrame, thx_hi: int) -> pd.DataFrame:
    """cross required variables
    to create design df (containing all relevant combinations)

    Parameters
    ----------
    df_survival_agg : pd.DataFrame
        df with aggregated info about survival
    thx_hi : int
        upper thx of nr. days followed up after nca

    Returns
    -------
    pd.DataFrame
        design df
    """
    df_days = pd.DataFrame({"n_days_to_invalid": range(1, thx_hi)})
    df_groups = pd.DataFrame(
        {"group_name": df_survival_agg["group_name"].unique()}
    )
    df_cohorts = pd.DataFrame({"cohort": df_survival_agg["cohort"].unique()})
    df_status_full = pd.DataFrame(
        {"status_full": df_survival_agg["status_full"].cat.categories}
    )
    df_design = reduce(
        lambda x, y: pd.merge(x, y, how="cross"),
        [df_groups, df_cohorts, df_days, df_status_full]
    )
    return df_design


import qgrid


def nca_overview(df_status_agg: pd.DataFrame):
    qgrid_widget = qgrid.show_grid(
        df_status_agg[[
            "cohort", "group_name", "status_full", "n_accounts", "prop_accounts"
        ]].rename(
            columns={
                "cohort": "Cohort",
                "group_name": "Group Name",
                "status_full": "Status",
                "n_accounts": "Nr. Accounts",
                "prop_accounts": "Prop. Accounts"
            }
        ).reset_index(drop=True).copy()
    )
    return qgrid_widget


def survival_overview(df_survival_agg: pd.DataFrame):
    qgrid_widget = qgrid.show_grid(
        (
            df_survival_agg[np.mod(df_survival_agg["n_days_to_invalid"], 365) ==
                            0].reset_index(drop=True)[[
                                "cohort", "group_name", "n_days_to_invalid",
                                "status_full", "n_accounts_tot", "prop_survive"
                            ]].rename(
                                columns={
                                    "cohort": "Cohort",
                                    "group_name": "Group",
                                    "n_days_to_invalid": "Nr. Days Since NCA",
                                    "status_full": "Status",
                                    "n_accounts_tot": "Nr. Accounts Start",
                                    "prop_survive": "Prop. Survive"
                                }
                            )
        )
    )
    return qgrid_widget


def plot_survival(df_survival_agg: pd.DataFrame) -> plt.axes:
    """plot survival curves by cohort, group, and status

    Parameters
    ----------
    df_survival_agg : pd.DataFrame
        df grouped by cohort, group, status and n days since nca with prop. valid as column

    Returns
    -------
    plt.axes
        faceted plot
    """
    with sns.axes_style("white") as s:
        df_survival_agg["Group"] = df_survival_agg["group_name"]
        g = sns.FacetGrid(
            df_survival_agg, row="status_full", col="cohort", hue="Group"
        )
        g.map(sns.lineplot, "n_days_to_invalid", "prop_survive")
        n_yrs = int(np.floor(df_survival_agg["max_n_days"].max() / 365))
        for yr in range(n_yrs):
            for ax in g.axes_dict.values():
                ax.axvline(
                    365 * (yr + 1),
                    0,
                    1,
                    alpha=.5,
                    color="grey",
                    linestyle="--",
                    linewidth=.75
                )
                if yr == 0:
                    ax.yaxis.grid()
                if yr == max(range(n_yrs)):
                    ax.set_xticks(
                        [(y + 1) * 365 for y in range(n_yrs)], minor=False
                    )
        g.set_titles(row_template='{row_name}', col_template='{col_name}')
        g.add_legend()
        plt.ylim(0, 1)
        _ = g.set_axis_labels("Days passed since NCA", "Proportion Survival")
    return g