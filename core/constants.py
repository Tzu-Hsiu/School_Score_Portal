# Subjects that are aggregate metrics, not individual exam subjects
EXCLUDE_STATS = ['總分', '平均', '班排', '校排']

# Rank metrics where "lower is better"
RANK_METRICS = ['班排', '校排']

# Score distribution bins
SCORE_BINS = [-1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
SCORE_BIN_LABELS = ['0-10', '11-20', '21-30', '31-40', '41-50', '51-60', '61-70', '71-80', '81-90', '91-100']

# School-wide total student count (used for school rank percentile)
DEFAULT_SCHOOL_TOTAL_STUDENTS = 520
