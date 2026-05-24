from enum import Enum
from typing import List, Optional, Literal

from pydantic import BaseModel, ConfigDict, Field


class ReaderDirectionEnum(str, Enum):
    """Direction in which authentication readers are installed on a door."""

    IN_ONLY = "IN_ONLY"
    OUT_ONLY = "OUT_ONLY"
    IN_OUT = "IN_OUT"
    NONE = "NONE"


class LockTypeEnum(str, Enum):
    """Type of access control lock installed on the door."""

    SOLENOID_LOCK = "SOLENOID_LOCK"
    ELECTRIC_STRIKE_PLATE = "ELECTRIC_STRIKE_PLATE"
    MAGNETIC_LOCK = "MAGNETIC_LOCK"
    MOTORIZED_LOCK = "MOTORIZED_LOCK"
    OTHER = "OTHER"
    NONE = "NONE"


class ReaderTypeEnum(str, Enum):
    """Authentication technology used by the reader device."""

    CARD = "CARD"
    CODE = "CODE"
    FINGERPRINT = "FINGERPRINT"
    FACE_RECOGNITION = "FACE_RECOGNITION"
    IRIS_SCAN = "IRIS_SCAN"
    BLUETOOTH = "BLUETOOTH"
    NFC = "NFC"
    WIRELESS_KEYFOB = "WIRELESS_KEYFOB"
    MOBILE_APP = "MOBILE_APP"
    LICENSEPLATE_CAMERA = "LICENSEPLATE_CAMERA"
    INTERCOM = "INTERCOM"
    OTHER = "OTHER"


class DoorCloserEnum(str, Enum):
    """Type of door closer installed on the door."""

    NONE = "NONE"
    MECHANICAL = "MECHANICAL"
    ELECTRIC = "ELECTRIC"


class EmergencyButtonEnum(str, Enum):
    """Emergency release device for the door."""

    NONE = "NONE"
    STANDALONE = "STANDALONE"
    INTRUSION = "INTRUSION"


class ExitDeviceEnum(str, Enum):
    """Device used to trigger exit from the secure side."""

    NONE = "NONE"
    PUSH_BUTTON = "PUSH_BUTTON"
    ELBOW_ACTUATED = "ELBOW_ACTUATED"
    GROUND_LOOP = "GROUND_LOOP"
    MOTION_SENSOR = "MOTION_SENSOR"


class PlacementSideHintEnum(str, Enum):
    """Optional relative-side hint for projected door accessories."""

    UNSPECIFIED = "UNSPECIFIED"
    SAME_AS_READER = "SAME_AS_READER"
    OPPOSITE_AS_READER = "OPPOSITE_AS_READER"
    BOTH = "BOTH"


class ControllerConnectionEnum(str, Enum):
    """How a controller communicates with doors/readers."""

    LAN = "LAN"
    BUS = "BUS"
    WIRELESS = "WIRELESS"
    HYBRID = "HYBRID"


class DoorRule(BaseModel):
    """Defines the access control configuration for one or more doors."""

    model_config = ConfigDict(extra="forbid")

    areas: List[str] = Field(
        default_factory=list,
        description=(
            "Space names this rule applies to. A door matches when either of its "
            "adjacent spaces appears in this list (case-insensitive substring)."
        ),
    )

    door_id: Optional[str] = Field(
        default=None,
        description=(
            "Explicit ID of a single door to target. Use only when the requirement "
            "identifies one specific door by name or ID. Prefer areas-based rules "
            "when multiple doors share the same configuration."
        ),
    )

    connects_to_areas: List[str] = Field(
        default_factory=list,
        description=(
            "When set together with areas, only doors that directly connect a space "
            "in areas to a space in connects_to_areas are matched (bidirectional). "
            "Use this to target the boundary door between two specific spaces."
        ),
    )

    reader_direction: Optional[ReaderDirectionEnum] = Field(
        default=None,
        description="Direction in which readers are installed",
    )

    reader_types: List[ReaderTypeEnum] = Field(
        default_factory=list,
        description="Authentication technologies used on the door",
    )

    lock_type: Optional[LockTypeEnum] = Field(
        default=None,
        description="Type of lock installed on the door",
    )

    door_closer: Optional[DoorCloserEnum] = Field(
        default=None,
        description="Type of door closer installed",
    )

    exit_device: Optional[ExitDeviceEnum] = Field(
        default=None,
        description="Exit trigger device on the secure side",
    )

    emergency_button: Optional[EmergencyButtonEnum] = Field(
        default=None,
        description="Emergency release device on the non-secure side",
    )

    exit_device_side_hint: Optional[PlacementSideHintEnum] = Field(
        default=None,
        description=(
            "Optional placement hint for exit devices. Use this only when the source text explicitly states the side."
        ),
    )

    emergency_button_side_hint: Optional[PlacementSideHintEnum] = Field(
        default=None,
        description=(
            "Optional placement hint for emergency buttons. Use this only when the source text explicitly states the side."
        ),
    )

    door_sensor: Optional[bool] = Field(
        default=None,
        description="Indicates whether the door has an open/close sensor",
    )

    anti_passback: Optional[bool] = Field(
        default=None,
        description="Whether anti-passback logic is enabled",
    )

    description: str = Field(
        description="Human-readable summary of the rule",
    )


class ControllerRule(BaseModel):
    """Defines which DoorRule areas are managed by a specific controller."""

    model_config = ConfigDict(extra="forbid")

    areas: List[str] = Field(
        default_factory=list,
        description="Physical location(s) where controller hardware is installed",
    )

    manages_door_areas: List[str] = Field(
        default_factory=list,
        description="DoorRule area names this controller manages",
    )

    connection_type: Optional[ControllerConnectionEnum] = Field(
        default=None,
        description="How controller communicates with doors/readers",
    )

    description: str = Field(
        description="Human-readable summary of the rule",
    )


class Requirements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    door_rules: List[DoorRule] = Field(default_factory=list)
    controller_rules: List[ControllerRule] = Field(default_factory=list)


class AccessControlSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system_type: Literal["ACCESS_CONTROL"] = "ACCESS_CONTROL"
    version: str = Field(default="1.0")
    requirements: Requirements
