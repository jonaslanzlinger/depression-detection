"""Type-tolerant matching for the polymorphic user_id field.

user_id is stored with different BSON types depending on mode: string UUIDs for
live users, string names for demo (e.g. "Alice"), and integers for the dataset
mode (e.g. 361). REST query params always arrive as strings, so a numeric id like
"361" would never match an int 361 in Mongo -> queries silently return nothing.

`user_id_match(user_id)` returns a value suitable for a Mongo equality filter that
matches both the string and the int form when the id is numeric, and matches as-is
for non-numeric ids (UUIDs, names). Use it as: find({"user_id": user_id_match(uid)}).
"""


def _is_int_like(s: str) -> bool:
    s = s.strip()
    if not s:
        return False
    body = s[1:] if s[0] in "+-" else s
    return body.isdigit()


def user_id_match(user_id):
    candidates = [user_id]
    # bool is a subclass of int; never treat it as a user id form
    if isinstance(user_id, str):
        if _is_int_like(user_id):
            candidates.append(int(user_id))
    elif isinstance(user_id, int) and not isinstance(user_id, bool):
        candidates.append(str(user_id))

    deduped = []
    for c in candidates:
        if c not in deduped:
            deduped.append(c)
    return deduped[0] if len(deduped) == 1 else {"$in": deduped}
