
IF OBJECT_ID('tempdb..#affinity_tmp') IS NOT NULL
	DROP TABLE #affinity_tmp
;

SELECT		ar.konto_lauf_id
			, ar.jamo
			, affinity_name = aff.affinity_name
			, avh.affinity_label
			, ar.affinity_value_trx
into		#affinity_tmp
FROM		jemas_temp.thm.affinity_results as ar
JOIN		jemas_temp.thm.affinities AS aff
	ON		aff.affinity_id = ar.affinity_id
JOIN		jemas_temp.thm.affinity_value_help AS avh
	ON		avh.affinity_value = ar.affinity_value_trx
JOIN		jemas_history.dbo.konto_jamo AS kj
	ON		kj.jamo = ar.jamo
	AND		kj.konto_lauf_id = ar.konto_lauf_id
where		kj.jamo in (201812, 201912, 202012)
and			kj.zustand_id <= 3
;

DECLARE      @cols AS NVARCHAR(MAX),
             @query  AS NVARCHAR(MAX),
			 @create_tbl AS NVARCHAR(MAX);

SET @cols = STUFF(
				(
				SELECT		DISTINCT ',' + QUOTENAME(affinity_name)
				FROM		#affinity_tmp FOR XML PATH(''), TYPE
				).value( '.', 'NVARCHAR(MAX)' ) ,1,1,'' 
			)

if object_id('tempdb.dbo.##affinity_pivot', 'u') is not null drop table ##affinity_pivot
;


SET @query = N'


SELECT		[konto_lauf_id], [jamo], ' + @cols + '
into		##affinity_pivot
FROM		( SELECT [konto_lauf_id], [jamo], [affinity_name], [affinity_label] FROM #affinity_tmp) t
PIVOT		( MAX( [affinity_label] ) FOR [affinity_name] IN (' + @cols + ') ) p
';

EXEC( @query )
;
