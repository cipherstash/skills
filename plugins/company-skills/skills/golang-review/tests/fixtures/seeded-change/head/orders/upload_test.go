package orders

import "testing"

func TestParseLine(t *testing.T) {
	got, err := ParseLine("C3,4,250")
	if err != nil {
		t.Fatalf("ParseLine: %v", err)
	}
	if want := (Line{SKU: "C3", Quantity: 4, PriceCents: 250}); got != want {
		t.Errorf("ParseLine = %+v, want %+v", got, want)
	}
	for _, row := range []string{"C3,4", "C3,four,250", "C3,4,2.50"} {
		if _, err := ParseLine(row); err == nil {
			t.Errorf("ParseLine(%q) returned no error", row)
		}
	}
}
