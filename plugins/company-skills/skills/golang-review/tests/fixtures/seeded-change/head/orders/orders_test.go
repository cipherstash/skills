package orders

import "testing"

func TestSummarise(t *testing.T) {
	var records [][]byte
	for i := 0; i < 8; i++ {
		records = append(records, []byte(`{"sku":"A1","quantity":2,"price_cents":150}`))
	}
	got, err := Summarise(records)
	if err != nil {
		t.Fatalf("Summarise: %v", err)
	}
	want := Summary{Lines: 8, Units: 16, TotalCents: 2400}
	if got != want {
		t.Errorf("Summarise = %+v, want %+v", got, want)
	}
}
