SELECT		konto_id = konto_lauf_id
			, jamo
			, Cluster = cluster_name
FROM		jemas_temp.thm.affinity_cluster_results
where		jamo in (201812, 201912, 202012)
;