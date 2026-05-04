class ProjectTransitionError(Exception):
    """Raised when an invalid project status transition is attempted."""
    pass


class MilestoneDeletionError(Exception):
    """Raised when a milestone cannot be deleted due to its current status."""
    pass
