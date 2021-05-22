USE jemas_temp;
go

IF NOT EXISTS (      SELECT       type_desc, type
                     FROM         sys.procedures WITH(NOLOCK)
                     WHERE        NAME = 'sp_survival_default'
                            AND          type = 'P'
              )
BEGIN
	EXECUTE('CREATE PROCEDURE thm.[sp_survival_default] as SELECT 1 as t');
END;
GO

alter PROCEDURE thm.sp_survival_default @dt_start_incl date
										, @dt_end_incl date
										, @sql_groups nvarchar(4000)
AS

if OBJECT_ID ('jemas_temp.thm.survival_default', 'u') is not null
	drop table jemas_temp.thm.survival_default
if OBJECT_ID ('tempdb.dbo.#ncas', 'u') is not null
	drop table #ncas
;

--declare @dt_start_incl date = '2017-01-01'
--		, @dt_end_incl date = '2018-12-31'
--		, @sql_groups nvarchar(max)
--;

--set @sql_groups = '
--				    SELECT		konto_id
--								, inhaber_nr
--								, group_name = distributionsdisziplin
--					FROM		jemas_report.dbo.R532_NCA_Report
--					where		konto_id is not null
--					and			kanal = ''Online-Antrag''
--				  '
--;


---------------------------------------------------------------------------------------------------------------------------------
--	groups
---------------------------------------------------------------------------------------------------------------------------------

if OBJECT_ID ('tempdb.dbo.#groups', 'u') is not null
	drop table #groups
;

create table #groups (
	konto_id int
	, inhaber_nr int
	, group_name nvarchar(50)
)
;

insert into #groups
exec sp_executesql @sql_groups
;

---------------------------------------------------------------------------------------------------------------------------------
--	ncas
---------------------------------------------------------------------------------------------------------------------------------

SELECT		a.*
into		#ncas
FROM		(
			SELECT		nca.konto_id
						, nca.CREATED_DT
						, nca.erfassung_antrag_datum
						, nca.bearbeitet_datum
						, nca.bearbeitet_jamo
						, nca.APPLICATION_FORM
						, nca.CRIF_RESULT
						, status_full = case
											when nca.status = 'Approved' and nca.ist_CCL = 0 and nca.ist_prepaid = 0 then 'Approved CCF'
											when nca.status = 'Approved' and nca.ist_prepaid = 1 then 'Approved PP'
											when nca.status = 'Approved' and nca.ist_CCL = 1 and nca.ist_CCL_downgrade = 0 then 'Approved CCL'
											when nca.status = 'Approved' and nca.ist_CCL = 1 and nca.ist_CCL_downgrade = 1 then 'Fallback CCL'
											when nca.status = 'Fallback' then 'Fallback PP'
											when nca.status = 'Rejected' and nca.ist_CCL = 1 then 'Rejected CCL'
											when nca.status = 'Rejected' and nca.ist_CCL = 0 then 'Rejected CCF'
											else 'Error'
										end
						, vp.produkt
						, vp.produkt_FC
						, vp.mandant
						, vp.kartenprofil
						, g.group_name
						, rwn = ROW_NUMBER() OVER(PARTITION BY nca.konto_id ORDER BY nca.status, nca.bearbeitet_datum)
			FROM		jemas_report.dbo.R532_NCA_Report as nca
			LEFT JOIN	jemas_history.dbo.konto_jamo AS kj
				ON		kj.konto_id = nca.konto_id
				AND		kj.jamo = nca.bearbeitet_jamo
			JOIN		(
						SELECT		distinct
									produkt_id
									, produkt
									, produkt_id_FC
									, produkt_FC
									, mandant_id
									, mandant
									, kartenprofil
						FROM		jemas_base.dbo.v_produkt
						) AS vp
				ON		vp.produkt_id = kj.produkt_id
			JOIN		#groups AS g
				ON		g.konto_id = nca.konto_id
				AND		g.inhaber_nr = nca.inhaber_nr
			where		nca.ist_bearbeitet_zuordnung_unmoeglich = 0
			and			nca.ist_Bestandeskunden_ZKI_Antrag = 0
			and			nca.status != 'Pending'
			and			nca.ist_hk_inhaber = 1
			) as a
where		a.rwn = 1
and			a.bearbeitet_datum >= @dt_start_incl
and			a.bearbeitet_datum <= @dt_end_incl
;

---------------------------------------------------------------------------------------------------------------------------------
--	churn
---------------------------------------------------------------------------------------------------------------------------------

if OBJECT_ID ('tempdb.dbo.#churn', 'u') is not null
	drop table #churn
;

SELECT		nca.konto_id
			, dt_cancelled = min(vkh.datenstand_jecas_datum)
			, n_days_to_invalid = DATEDIFF(day, nca.bearbeitet_datum, min(vkh.datenstand_jecas_datum))
into		#churn
FROM		#ncas as nca
LEFT JOIN	jemas_history.dbo.v_konto_history AS vkh
	ON		vkh.konto_id = nca.konto_id
	AND		vkh.datenstand_Jecas_datum >= nca.bearbeitet_datum
where		vkh.kontostatus_id between 30 and 89
group BY	nca.konto_id
			, nca.bearbeitet_datum
;

---------------------------------------------------------------------------------------------------------------------------------
--	turnover
---------------------------------------------------------------------------------------------------------------------------------

if OBJECT_ID ('tempdb.dbo.#sf', 'u') is not null
	drop table #sf
;

SELECT		nca.konto_id
			, jamo = YEAR(sf.erfassung_datum)*100+MONTH(sf.erfassung_datum)
			, n_trx = count(sf.betrag)
			, sum_turnover = sum(sf.betrag)
into		#sf
FROM		#ncas as nca
JOIN		jemas_base.dbo.sales_fact AS sf
	ON		sf.konto_id = nca.konto_id
	AND		sf.erfassung_datum >= nca.bearbeitet_datum
where		sf.ist_umsatz = 1
GROUP BY	nca.konto_id
			, YEAR(sf.erfassung_datum)*100+MONTH(sf.erfassung_datum)
;

---------------------------------------------------------------------------------------------------------------------------------
--	feature market
---------------------------------------------------------------------------------------------------------------------------------

if OBJECT_ID ('tempdb.dbo.#kj', 'u') is not null
	drop table #kj
;
SELECT		nca.*
			, kj.jamo
			, is_valid = case when kj.zustand_id <= 3 then 1 else 0 end
into		#kj
FROM		#ncas as nca
LEFT JOIN	jemas_history.dbo.konto_jamo AS kj
	ON		kj.konto_id = nca.konto_id
	AND		kj.jamo >= nca.bearbeitet_jamo
;

if OBJECT_ID ('tempdb.dbo.#fmkj', 'u') is not null
	drop table #fmkj
;

SELECT		kj.konto_id
			, kj.jamo
			, fmkj.cm1
			, fmkj.payment_type_segment
			, fmkj.financial_profile_segment
into		#fmkj
FROM		#kj as kj
LEFT JOIN	if_core.calc.feature_market_konto_jamo AS fmkj
	ON		fmkj.konto_id = kj.konto_id
	AND		fmkj.jamo = kj.jamo
;

---------------------------------------------------------------------------------------------------------------------------------
--	wrap-up
---------------------------------------------------------------------------------------------------------------------------------

SELECT		kj.konto_id
			, kj.jamo
			, kj.is_valid
			, nca.APPLICATION_FORM
			, nca.CRIF_RESULT
			, nca.CREATED_DT
			, nca.erfassung_antrag_datum
			, nca.bearbeitet_datum
			, nca.bearbeitet_jamo
			, nca.status_full
			, nca.produkt
			, nca.produkt_FC
			, nca.mandant
			, nca.kartenprofil
			, nca.group_name
			, ch.dt_cancelled
			, ch.n_days_to_invalid
			, sf.n_trx
			, sf.sum_turnover
			, fmkj.cm1
			, fmkj.payment_type_segment
			, fmkj.financial_profile_segment
			, month_nr = ROW_NUMBER() OVER(PARTITION BY kj.konto_id ORDER BY kj.jamo)
into		jemas_temp.thm.survival_default
FROM		#kj as kj
LEFT JOIN	#ncas AS nca
	ON		nca.konto_id = kj.konto_id
LEFT JOIN	#churn AS ch
	ON		ch.konto_id = kj.konto_id
LEFT JOIN	#sf AS sf
	ON		sf.konto_id = kj.konto_id
	AND		sf.jamo = kj.jamo
LEFT JOIN	#fmkj AS fmkj
	ON		fmkj.konto_id = kj.konto_id
	AND		fmkj.jamo = kj.jamo
;
