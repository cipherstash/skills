package performance

import (
	"strconv"
	"strings"
)

// User is a record to export.
type User struct {
	ID   int64
	Name string
}

// IDs returns the IDs of users. The length is known, so the slice is made
// with that capacity once instead of growing and copying as append fills it.
func IDs(users []User) []int64 {
	ids := make([]int64, 0, len(users))
	for _, u := range users {
		ids = append(ids, u.ID)
	}
	return ids
}

// ByID indexes users by ID. The size hint lets the map allocate its buckets
// once.
func ByID(users []User) map[int64]User {
	m := make(map[int64]User, len(users))
	for _, u := range users {
		m[u.ID] = u
	}
	return m
}

// JoinNamesConcat joins names with +=. Each += copies the whole string built
// so far, so the work grows with the square of the input. Shown for the
// benchmark; use JoinNames.
func JoinNamesConcat(users []User) string {
	s := ""
	for i, u := range users {
		if i > 0 {
			s += ","
		}
		s += u.Name
	}
	return s
}

// JoinNames joins names with a strings.Builder, which appends to one growing
// buffer. strings.Join does the same for a []string.
func JoinNames(users []User) string {
	var b strings.Builder
	for i, u := range users {
		if i > 0 {
			b.WriteByte(',')
		}
		b.WriteString(u.Name)
	}
	return b.String()
}

// AppendCSV appends u as a CSV line to dst and returns the extended slice.
// A caller that writes many records reuses one buffer, so the hot loop does
// not allocate. strconv.AppendInt formats without making a string first.
// Names are written as they are: this example assumes they hold no commas.
func AppendCSV(dst []byte, u User) []byte {
	dst = strconv.AppendInt(dst, u.ID, 10)
	dst = append(dst, ',')
	dst = append(dst, u.Name...)
	return append(dst, '\n')
}
