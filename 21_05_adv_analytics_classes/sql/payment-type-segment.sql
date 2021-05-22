SELECT		fmkj.konto_id
			, kj.konto_lauf_id
			, fmkj.jamo
			, 'Payment Type Segment' = ivh.indicator_label
FROM		jemas_history.dbo.konto_jamo as kj
JOIN		if_core.calc.feature_market_konto_jamo as fmkj
	ON		fmkj.konto_id = kj.konto_id
	AND		fmkj.jamo = kj.jamo
JOIN		(
			SELECT		ivh.*
			FROM		if_core.calc.indicator_value_help AS ivh
			JOIN		if_core.calc.indicator AS i
				ON		i.indicator_id = ivh.indicator_id
			where		i.indicator_name_en = 'payment_type_segment'
			) as ivh
	ON		ivh.indicator_value = fmkj.payment_type_segment
where		kj.jamo in (201812, 201912, 202012)
and			kj.zustand_id <= 3
;
