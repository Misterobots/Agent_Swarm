"""Pioneer persona pool and perspective taxonomy for Lamport workers."""

WORKER_PIONEERS: dict[str, list[dict]] = {
    "researcher": [
        {"name": "Shannon",  "full_name": "Claude Shannon",     "motto": "Information is the resolution of uncertainty."},
        {"name": "Minsky",   "full_name": "Marvin Minsky",      "motto": "Minds are what brains do."},
        {"name": "Johnson",  "full_name": "Katherine Johnson",  "motto": "Like what you do, and then you will do your best."},
    ],
    "architect": [
        {"name": "Babbage",  "full_name": "Charles Babbage",    "motto": "Errors using inadequate data are far less than those using no data at all."},
        {"name": "Dijkstra", "full_name": "Edsger Dijkstra",    "motto": "Simplicity is a prerequisite for reliability."},
        {"name": "Hamilton", "full_name": "Margaret Hamilton",  "motto": "There was no choice but to be pioneers."},
    ],
    "coder": [
        {"name": "Knuth",    "full_name": "Donald Knuth",      "motto": "Programs are meant to be read by humans."},
        {"name": "Lovelace", "full_name": "Ada Lovelace",       "motto": "The Analytical Engine weaves algebraic patterns just as the Jacquard loom weaves flowers."},
        {"name": "Ritchie",  "full_name": "Dennis Ritchie",     "motto": "UNIX is basically a simple operating system, but you have to be a genius to understand the simplicity."},
    ],
    "devops": [
        {"name": "Cerf",     "full_name": "Vint Cerf",         "motto": "The internet is a reflection of our society."},
        {"name": "Torvalds", "full_name": "Linus Torvalds",    "motto": "Talk is cheap. Show me the code."},
        {"name": "Perlman",  "full_name": "Radia Perlman",     "motto": "The world would be a better place if more engineers cared about the broader context of their work."},
    ],
    "analyst": [
        {"name": "Codd",     "full_name": "Edgar Codd",         "motto": "Data is a precious thing and will last longer than the systems themselves."},
        {"name": "Hopper",   "full_name": "Grace Hopper",        "motto": "The most dangerous phrase in the language is: we've always done it this way."},
        {"name": "Boole",    "full_name": "George Boole",        "motto": "No matter how correct a mathematical theorem may appear, it may be disproved by a single contradiction."},
    ],
    "verifier": [
        {"name": "Hoare",  "full_name": "Tony Hoare",        "motto": "There are two ways to write error-free programs; only the third works."},
        {"name": "Turing", "full_name": "Alan Turing",       "motto": "We can only see a short distance ahead, but we can see plenty there that needs to be done."},
        {"name": "Liskov", "full_name": "Barbara Liskov",    "motto": "Abstraction is the key to simplicity."},
    ],
    "technical": [
        {"name": "Knuth",    "full_name": "Donald Knuth",      "motto": "Programs are meant to be read by humans."},
        {"name": "Dijkstra", "full_name": "Edsger Dijkstra",   "motto": "Simplicity is a prerequisite for reliability."},
        {"name": "Thompson", "full_name": "Ken Thompson",      "motto": "One of my most productive days was throwing away 1000 lines of code."},
    ],
    "ethical": [
        {"name": "Weil",     "full_name": "Simone Weil",       "motto": "Attention is the rarest and purest form of generosity."},
        {"name": "Rawls",    "full_name": "John Rawls",        "motto": "Justice is the first virtue of social institutions."},
        {"name": "Floridi",  "full_name": "Luciano Floridi",   "motto": "We are becoming informational organisms."},
    ],
    "economic": [
        {"name": "Keynes",   "full_name": "John M. Keynes",    "motto": "The difficulty lies not in the new ideas, but in escaping from the old ones."},
        {"name": "Ostrom",   "full_name": "Elinor Ostrom",     "motto": "A resource is not just physical — it is also institutional."},
        {"name": "Hayek",    "full_name": "Friedrich Hayek",   "motto": "The curious task of economics is to demonstrate how little men actually know."},
    ],
    "scientific": [
        {"name": "Curie",    "full_name": "Marie Curie",       "motto": "Nothing in life is to be feared, it is only to be understood."},
        {"name": "Feynman",  "full_name": "Richard Feynman",   "motto": "If you can't explain something simply, you don't understand it well enough."},
        {"name": "Sagan",    "full_name": "Carl Sagan",        "motto": "Extraordinary claims require extraordinary evidence."},
    ],
    "regulatory": [
        {"name": "Brandeis", "full_name": "Louis Brandeis",    "motto": "Sunlight is said to be the best of disinfectants."},
        {"name": "Nader",    "full_name": "Ralph Nader",       "motto": "The function of leadership is to produce more leaders, not more followers."},
        {"name": "Warren",   "full_name": "Elizabeth Warren",  "motto": "The system is rigged, but it doesn't have to stay that way."},
    ],
    "end_user": [
        {"name": "Norman",   "full_name": "Don Norman",        "motto": "Design is really an act of communication."},
        {"name": "Nielsen",  "full_name": "Jakob Nielsen",     "motto": "Usability is not a luxury, it is a basic condition for survival."},
        {"name": "Cooper",   "full_name": "Alan Cooper",       "motto": "No matter how cool your interface is, it would be better if there were less of it."},
    ],
    "historical": [
        {"name": "Braudel",  "full_name": "Fernand Braudel",   "motto": "History is the long memory of time."},
        {"name": "Kuhn",     "full_name": "Thomas Kuhn",       "motto": "Normal science does not aim at novelties of fact or theory."},
        {"name": "Durant",   "full_name": "Will Durant",       "motto": "The health of nations is more important than the wealth of nations."},
    ],
    "policy": [
        {"name": "Sen",      "full_name": "Amartya Sen",       "motto": "Development is freedom."},
        {"name": "Ostrom",   "full_name": "Elinor Ostrom",     "motto": "A resource is not just physical — it is also institutional."},
        {"name": "Sachs",    "full_name": "Jeffrey Sachs",     "motto": "The world has the knowledge and the resources to end extreme poverty."},
    ],
    "environmental": [
        {"name": "Carson",   "full_name": "Rachel Carson",     "motto": "The more clearly we can focus our attention on the wonders and realities of the universe, the less taste we shall have for destruction."},
        {"name": "Attenborough", "full_name": "David Attenborough", "motto": "It's surely our responsibility to do everything within our power to create a planet that provides a home not just for us, but for all life on Earth."},
        {"name": "Lovins",   "full_name": "Amory Lovins",      "motto": "Efficiency is doing things right; effectiveness is doing the right things."},
    ],
    "social": [
        {"name": "Du Bois",  "full_name": "W.E.B. Du Bois",   "motto": "The cost of liberty is less than the price of repression."},
        {"name": "Wollstonecraft", "full_name": "Mary Wollstonecraft", "motto": "I do not wish women to have power over men; but over themselves."},
        {"name": "Bourdieu", "full_name": "Pierre Bourdieu",   "motto": "The function of sociology is to unsettle the obvious."},
    ],
}

PERSPECTIVE_TAXONOMY: list[str] = [
    "technical", "ethical", "economic", "scientific",
    "regulatory", "end_user", "historical", "policy",
    "environmental", "social",
]


def _pioneer_for_role(role: str) -> dict:
    """Return the primary pioneer persona dict for a given worker role (no dedup)."""
    pool = WORKER_PIONEERS.get(role.lower())
    if pool:
        return pool[0]
    return {"name": role.title(), "full_name": role.title(), "motto": ""}


def _pick_unique_pioneer(role: str, used_names: set[str]) -> dict:
    """Pick the first pioneer from the pool whose name is not in used_names."""
    pool = WORKER_PIONEERS.get(role.lower(), [])
    for candidate in pool:
        if candidate["name"] not in used_names:
            return candidate
    base = pool[0] if pool else {"name": role.title(), "full_name": role.title(), "motto": ""}
    suffix = len([n for n in used_names if n.startswith(base["name"])]) + 1
    return {**base, "name": f"{base['name']}-{suffix}", "full_name": f"{base['full_name']} ({suffix})"}
