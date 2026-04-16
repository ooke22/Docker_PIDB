# ===== Helper Functions ========
def parse_range(range_str):
    """Parse comma-separated ranges like '1,3,5-7' into [1,3,5,6,7]"""
    if not range_str or not range_str.strip():
        return []
    
    result = []
    try:
        for ids in range_str.split(','):
            id = ids.strip()
            if '-' in id:
                start, end = map(int, id.split('-'))
                result.extend(range(start, end + 1))
            else:
                result.append(int(id))
    except (ValueError, TypeError):
        return []
    
    return result