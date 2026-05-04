class CostingSheetTransitionError(Exception):
    """Raised when an invalid Costing Sheet state transition is attempted."""
    pass


class DuplicateCostingSheetError(Exception):
    """Raised when a second Costing Sheet is created for the same Project."""
    pass


class DuplicatePOError(Exception):
    """Raised when a non-cancelled PO already exists for a Costing Sheet."""
    pass


class ClientNotificationRequiredError(Exception):
    """Raised when fulfillment is blocked by a pending client notification."""
    pass


class POTransitionError(Exception):
    """Raised when an invalid PO status transition is attempted."""
    pass
