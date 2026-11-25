package interfaces

import (
	"fmt"
	"strconv"
)

// Describe formats a value from a decoded JSON document. The type switch
// binds v to the concrete type in each case.
func Describe(value any) string {
	switch v := value.(type) {
	case nil:
		return "null"
	case string:
		return strconv.Quote(v)
	case float64:
		return strconv.FormatFloat(v, 'g', -1, 64)
	case bool:
		return strconv.FormatBool(v)
	case fmt.Stringer:
		return v.String()
	default:
		return fmt.Sprintf("%T", v)
	}
}
