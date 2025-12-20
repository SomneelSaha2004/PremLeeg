"""Team name mapping and matching utilities.

Maps common team name variations to the canonical names used in the database.
This helps the LLM generate correct SQL with exact team name matches.
"""

from typing import List, Optional, Tuple

# Canonical team names as they appear in the database
CANONICAL_TEAM_NAMES = [
    "Arsenal",
    "Aston Villa",
    "Barnsley",
    "Birmingham",
    "Blackburn",
    "Blackpool",
    "Bolton",
    "Bournemouth",
    "Bradford",
    "Brentford",
    "Brighton",
    "Burnley",
    "Cardiff",
    "Charlton",
    "Chelsea",
    "Coventry",
    "Crystal Palace",
    "Derby",
    "Everton",
    "Fulham",
    "Huddersfield",
    "Hull",
    "Ipswich",
    "Leeds",
    "Leicester",
    "Liverpool",
    "Luton",
    "Man City",
    "Man United",
    "Middlesbrough",
    "Newcastle",
    "Norwich",
    "Nott'm Forest",
    "Oldham",
    "Portsmouth",
    "QPR",
    "Reading",
    "Sheffield United",
    "Sheffield Weds",
    "Southampton",
    "Stoke",
    "Sunderland",
    "Swansea",
    "Swindon",
    "Tottenham",
    "Watford",
    "West Brom",
    "West Ham",
    "Wigan",
    "Wimbledon",
    "Wolves",
]

# Mapping of common aliases/variations to canonical names
TEAM_ALIASES = {
    # Arsenal
    "arsenal": "Arsenal",
    "the gunners": "Arsenal",
    "gunners": "Arsenal",
    "afc": "Arsenal",
    
    # Aston Villa
    "aston villa": "Aston Villa",
    "villa": "Aston Villa",
    "avfc": "Aston Villa",
    
    # Birmingham
    "birmingham": "Birmingham",
    "birmingham city": "Birmingham",
    "blues": "Birmingham",
    
    # Blackburn
    "blackburn": "Blackburn",
    "blackburn rovers": "Blackburn",
    "rovers": "Blackburn",
    
    # Blackpool
    "blackpool": "Blackpool",
    "the seasiders": "Blackpool",
    
    # Bolton
    "bolton": "Bolton",
    "bolton wanderers": "Bolton",
    
    # Bournemouth
    "bournemouth": "Bournemouth",
    "afc bournemouth": "Bournemouth",
    "the cherries": "Bournemouth",
    "cherries": "Bournemouth",
    
    # Bradford
    "bradford": "Bradford",
    "bradford city": "Bradford",
    
    # Brentford
    "brentford": "Brentford",
    "the bees": "Brentford",
    "bees": "Brentford",
    
    # Brighton
    "brighton": "Brighton",
    "brighton and hove albion": "Brighton",
    "brighton & hove albion": "Brighton",
    "seagulls": "Brighton",
    
    # Burnley
    "burnley": "Burnley",
    "the clarets": "Burnley",
    "clarets": "Burnley",
    
    # Cardiff
    "cardiff": "Cardiff",
    "cardiff city": "Cardiff",
    "bluebirds": "Cardiff",
    
    # Charlton
    "charlton": "Charlton",
    "charlton athletic": "Charlton",
    "addicks": "Charlton",
    
    # Chelsea
    "chelsea": "Chelsea",
    "the blues": "Chelsea",
    "cfc": "Chelsea",
    
    # Coventry
    "coventry": "Coventry",
    "coventry city": "Coventry",
    "sky blues": "Coventry",
    
    # Crystal Palace
    "crystal palace": "Crystal Palace",
    "palace": "Crystal Palace",
    "eagles": "Crystal Palace",
    "cpfc": "Crystal Palace",
    
    # Derby
    "derby": "Derby",
    "derby county": "Derby",
    "the rams": "Derby",
    "rams": "Derby",
    
    # Everton
    "everton": "Everton",
    "the toffees": "Everton",
    "toffees": "Everton",
    "efc": "Everton",
    
    # Fulham
    "fulham": "Fulham",
    "the cottagers": "Fulham",
    "cottagers": "Fulham",
    
    # Huddersfield
    "huddersfield": "Huddersfield",
    "huddersfield town": "Huddersfield",
    "the terriers": "Huddersfield",
    "terriers": "Huddersfield",
    
    # Hull
    "hull": "Hull",
    "hull city": "Hull",
    "the tigers": "Hull",
    "tigers": "Hull",
    
    # Ipswich
    "ipswich": "Ipswich",
    "ipswich town": "Ipswich",
    "tractor boys": "Ipswich",
    
    # Leeds
    "leeds": "Leeds",
    "leeds united": "Leeds",
    "lufc": "Leeds",
    
    # Leicester
    "leicester": "Leicester",
    "leicester city": "Leicester",
    "the foxes": "Leicester",
    "foxes": "Leicester",
    "lcfc": "Leicester",
    
    # Liverpool
    "liverpool": "Liverpool",
    "the reds": "Liverpool",
    "lfc": "Liverpool",
    
    # Luton
    "luton": "Luton",
    "luton town": "Luton",
    "the hatters": "Luton",
    "hatters": "Luton",
    
    # Manchester City
    "man city": "Man City",
    "manchester city": "Man City",
    "city": "Man City",
    "mcfc": "Man City",
    "citizens": "Man City",
    "the citizens": "Man City",
    
    # Manchester United
    "man united": "Man United",
    "manchester united": "Man United",
    "united": "Man United",
    "mufc": "Man United",
    "man utd": "Man United",
    "red devils": "Man United",
    "the red devils": "Man United",
    
    # Middlesbrough
    "middlesbrough": "Middlesbrough",
    "boro": "Middlesbrough",
    "the boro": "Middlesbrough",
    
    # Newcastle
    "newcastle": "Newcastle",
    "newcastle united": "Newcastle",
    "the magpies": "Newcastle",
    "magpies": "Newcastle",
    "nufc": "Newcastle",
    "toon": "Newcastle",
    
    # Norwich
    "norwich": "Norwich",
    "norwich city": "Norwich",
    "the canaries": "Norwich",
    "canaries": "Norwich",
    
    # Nottingham Forest
    "nott'm forest": "Nott'm Forest",
    "nottingham forest": "Nott'm Forest",
    "forest": "Nott'm Forest",
    "nffc": "Nott'm Forest",
    
    # Oldham
    "oldham": "Oldham",
    "oldham athletic": "Oldham",
    
    # Portsmouth
    "portsmouth": "Portsmouth",
    "pompey": "Portsmouth",
    
    # QPR
    "qpr": "QPR",
    "queens park rangers": "QPR",
    "queen's park rangers": "QPR",
    "rangers": "QPR",
    
    # Reading
    "reading": "Reading",
    "the royals": "Reading",
    "royals": "Reading",
    
    # Sheffield United
    "sheffield united": "Sheffield United",
    "sheffield utd": "Sheffield United",
    "the blades": "Sheffield United",
    "blades": "Sheffield United",
    "sufc": "Sheffield United",
    
    # Sheffield Wednesday
    "sheffield weds": "Sheffield Weds",
    "sheffield wednesday": "Sheffield Weds",
    "wednesday": "Sheffield Weds",
    "the owls": "Sheffield Weds",
    "owls": "Sheffield Weds",
    
    # Southampton
    "southampton": "Southampton",
    "the saints": "Southampton",
    "saints": "Southampton",
    
    # Stoke
    "stoke": "Stoke",
    "stoke city": "Stoke",
    "the potters": "Stoke",
    "potters": "Stoke",
    
    # Sunderland
    "sunderland": "Sunderland",
    "the black cats": "Sunderland",
    "black cats": "Sunderland",
    "safc": "Sunderland",
    
    # Swansea
    "swansea": "Swansea",
    "swansea city": "Swansea",
    "the swans": "Swansea",
    "swans": "Swansea",
    
    # Swindon
    "swindon": "Swindon",
    "swindon town": "Swindon",
    
    # Tottenham
    "tottenham": "Tottenham",
    "tottenham hotspur": "Tottenham",
    "spurs": "Tottenham",
    "thfc": "Tottenham",
    
    # Watford
    "watford": "Watford",
    "the hornets": "Watford",
    "hornets": "Watford",
    
    # West Brom
    "west brom": "West Brom",
    "west bromwich albion": "West Brom",
    "west bromwich": "West Brom",
    "the baggies": "West Brom",
    "baggies": "West Brom",
    "wba": "West Brom",
    
    # West Ham
    "west ham": "West Ham",
    "west ham united": "West Ham",
    "the hammers": "West Ham",
    "hammers": "West Ham",
    "whufc": "West Ham",
    "irons": "West Ham",
    
    # Wigan
    "wigan": "Wigan",
    "wigan athletic": "Wigan",
    "the latics": "Wigan",
    "latics": "Wigan",
    
    # Wimbledon
    "wimbledon": "Wimbledon",
    "the dons": "Wimbledon",
    "dons": "Wimbledon",
    
    # Wolves
    "wolves": "Wolves",
    "wolverhampton": "Wolves",
    "wolverhampton wanderers": "Wolves",
}


def find_team_in_question(question: str) -> Optional[str]:
    """
    Find a team name mentioned in the question and return the canonical name.
    
    Args:
        question: The user's question text
        
    Returns:
        The canonical team name if found, None otherwise
    """
    q_lower = question.lower()
    
    # First, try exact matches with canonical names (case-insensitive)
    for team in CANONICAL_TEAM_NAMES:
        if team.lower() in q_lower:
            return team
    
    # Then try aliases (sorted by length descending to match longer phrases first)
    sorted_aliases = sorted(TEAM_ALIASES.keys(), key=len, reverse=True)
    for alias in sorted_aliases:
        if alias in q_lower:
            return TEAM_ALIASES[alias]
    
    return None


def find_all_teams_in_question(question: str) -> List[str]:
    """
    Find all team names mentioned in the question.
    
    Args:
        question: The user's question text
        
    Returns:
        List of canonical team names found (may be empty)
    """
    q_lower = question.lower()
    found_teams = set()
    
    # Check canonical names
    for team in CANONICAL_TEAM_NAMES:
        if team.lower() in q_lower:
            found_teams.add(team)
    
    # Check aliases
    for alias, canonical in TEAM_ALIASES.items():
        if alias in q_lower:
            found_teams.add(canonical)
    
    return list(found_teams)


def get_team_filter_hint(question: str) -> Optional[str]:
    """
    Generate a hint for the LLM about team filtering.
    
    Args:
        question: The user's question text
        
    Returns:
        A hint string about team filtering, or None if no team found
    """
    teams = find_all_teams_in_question(question)
    
    if not teams:
        return None
    
    if len(teams) == 1:
        team = teams[0]
        return (
            f"TEAM FILTER: The question mentions '{team}'. "
            f"Use WHERE team = '{team}' (exact match, case-sensitive)."
        )
    else:
        team_list = ", ".join(f"'{t}'" for t in teams)
        return (
            f"TEAM FILTER: The question mentions multiple teams: {team_list}. "
            f"Use WHERE team IN ({team_list}) (exact match, case-sensitive)."
        )
