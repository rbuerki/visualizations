SELECT		konto_id
			, inhaber_nr
			, group_name = distributionsdisziplin
FROM		jemas_report.dbo.R532_NCA_Report
where		konto_id is not null
and			kanal = 'Online-Antrag'
