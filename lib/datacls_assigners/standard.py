from lib.string_manipulations.string_transforms.mechanisms import (
    PrefixRemover,
    UpperTransform,
)
from lib.string_manipulations.string_transforms.scaffold import SequenceTransform

from .protocol import DataclsAssignerProtocol
from .scaffold import ScaffoldDataclsAssigner


class StandardDataclsAssigner(DataclsAssignerProtocol):
    def __call__(self, *, datacls, data, coercer, extra_keys_allowed):
        parent = ScaffoldDataclsAssigner(
            class_key_projection=SequenceTransform(
                transforms=[
                    PrefixRemover(prefix="_"),
                    UpperTransform(),
                ]
            ),
            data_key_projection=UpperTransform(),
        )

        return parent.__call__(
            datacls=datacls,
            data=data,
            coercer=coercer,
            extra_keys_allowed=extra_keys_allowed,
        )
