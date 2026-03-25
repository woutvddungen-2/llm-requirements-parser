from enum import Enum
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


class ReaderDirectionEnum(str, Enum):
    """
    Direction in which authentication readers are installed on a door.
    """
    IN_ONLY = "IN_ONLY"        # reader on non-secure side only
    OUT_ONLY = "OUT_ONLY"      # reader on secure side only
    IN_OUT = "IN_OUT"          # readers on both sides
    NONE = "NONE"              # no reader


class LockTypeEnum(str, Enum):
    """
    Type of access control lock installed on the door.
    """
    SOLENOID_LOCK = "SOLENOID_LOCK"
    ELECTRIC_STRIKE_PLATE = "ELECTRIC_STRIKE_PLATE"
    MAGNETIC_LOCK = "MAGNETIC_LOCK"
    MOTORIZED_LOCK = "MOTORIZED_LOCK"
    OTHER = "OTHER"
    NONE = "NONE"


class ReaderTypeEnum(str, Enum):
    """
    Authentication technology used by the reader device.
    """
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
    OTHER = "OTHER"


class DoorCloserEnum(str, Enum):
    """
    Type of door closer installed on the door.
    """
    NONE = "NONE"
    MECHANICAL = "MECHANICAL"
    ELECTRIC = "ELECTRIC"


class EmergencyButtonEnum(str, Enum):
    """
    Emergency release device for the door.
    """
    NONE = "NONE"
    STANDALONE = "STANDALONE" # a standalone emergency button that releases the lock
    INTRUSION = "INTRUSION" # integrated with intrusion alarm system


class ExitDeviceEnum(str, Enum):
    """
    Device used to trigger exit from the secure side.
    """
    NONE = "NONE"
    PUSH_BUTTON = "PUSH_BUTTON"
    ELBOW_ACTUATED = "ELBOW_ACTUATED"
    GROUND_LOOP = "GROUND_LOOP"
    MOTION_SENSOR = "MOTION_SENSOR"


class DoorRule(BaseModel):
    """
    Defines the access control configuration for one or more groups of doors.
    """

    model_config = ConfigDict(extra="forbid")

    areas: List[str] = Field(
        min_length=1,
        default_factory=list,
        description="Door groups or areas to which this rule applies"
    )

    reader_direction: Optional[ReaderDirectionEnum] = Field(
        default=None,
        description="Direction in which readers are installed"
    )

    reader_types: List[ReaderTypeEnum] = Field(
        default_factory=list,
        description="Authentication technologies used on the door"
    )

    lock_type: Optional[LockTypeEnum] = Field(
        default=None,
        description="Type of lock installed on the door"
    )

    door_closer: Optional[DoorCloserEnum] = Field(
        default=None,
        description="Type of door closer installed"
    )

    exit_device: Optional[ExitDeviceEnum] = Field(
        default=None,
        description="Exit trigger device on the secure side"
    )

    emergency_button: Optional[EmergencyButtonEnum] = Field(
        default=None,
        description="Emergency release device"
    )

    door_sensor: Optional[bool] = Field(
        default=None,
        description="Indicates whether the door has an open/close sensor"
    )

    anti_passback: Optional[bool] = Field(
        default=None,
        description="Whether anti-passback logic is enabled"
    )

    description: str = Field(
        description="Human-readable summary of the rule"
    )

class ControllerRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    areas: List[str] = Field(
        default_factory=list,
        description="Areas to which this controller rule applies",
    )

    door_count: int = Field(
        ge=1, le=99,
        description="Number of doors controlled by the controller",
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