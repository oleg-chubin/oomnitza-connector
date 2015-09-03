
import logging
logger = logging.getLogger("converters/split")


def converter(field, record, value, params):
    """
    Splits a value on a character.
    params:
        on: Required: character or string on which to split
        index: Optional: part to return, defaults to 0

    :param value: field value
    :return:
    """
#    logger.warn("converter(%r, %r, %r, %r)", field, record, value, params)

    try:
        split_on = params.get('on', None)
        index = int(params.get('index', 0))

        return value.split(split_on)[index]
    except:
        logger.exception("Error running split() converter on %r.", value)
        return value

