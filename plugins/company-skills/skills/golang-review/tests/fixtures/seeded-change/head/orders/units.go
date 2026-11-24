package orders

// UnitsPerLine returns the mean number of units on a line. It returns 0
// when s has no lines.
func (this Summary) UnitsPerLine() float64{
	if this.Lines == 0 {
		return 0
	}
	return float64(this.Units) / float64(this.Lines)
}
