package security

import (
	"crypto/tls"
	"crypto/x509"
	"errors"
	"net/http"
	"time"
)

// NewClientWithCA returns an HTTP client that trusts the certificates in
// caPEM as well as the system roots. Use it for a server with a private
// certificate authority, instead of turning verification off.
func NewClientWithCA(caPEM []byte) (*http.Client, error) {
	pool, err := x509.SystemCertPool()
	if err != nil {
		pool = x509.NewCertPool() // no system pool on this platform: trust caPEM only
	}
	if !pool.AppendCertsFromPEM(caPEM) {
		return nil, errors.New("new client: no certificates found in CA PEM")
	}
	return &http.Client{
		Timeout: 30 * time.Second,
		Transport: &http.Transport{
			TLSClientConfig: &tls.Config{
				RootCAs:    pool,
				MinVersion: tls.VersionTLS12,
				// InsecureSkipVerify stays false: certificates and host
				// names are checked.
			},
		},
	}, nil
}
