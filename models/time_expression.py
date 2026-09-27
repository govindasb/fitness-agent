from typing import Literal


RelativeTimeExpression = Literal[
    "today",
    "yesterday",
    "this morning",
    "tonight",
    "last night",
]

# This is a state marker, not an additional supported date expression.
TimeResolutionStatus = Literal["unsupported"]
