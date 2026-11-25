package security

import (
	"crypto/tls"
	"crypto/x509"
	"errors"
	"fmt"
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
	// Clone the default transport to keep its proxy settings, HTTP/2, and
	// timeouts. A bare &http.Transport{} has none of them. A program may have
	// replaced DefaultTransport with a wrapper, so check its type.
	base, ok := http.DefaultTransport.(*http.Transport)
	if !ok {
		return nil, fmt.Errorf("new client: http.DefaultTransport is %T, not *http.Transport", http.DefaultTransport)
	}
	transport := base.Clone()
	// Keep any TLS settings the program gave the default transport, such as a
	// client certificate or ServerName, and add the CA to them.
	tlsConfig := &tls.Config{}
	if base.TLSClientConfig != nil {
		tlsConfig = base.TLSClientConfig.Clone()
	}
	tlsConfig.RootCAs = pool
	tlsConfig.MinVersion = max(tlsConfig.MinVersion, tls.VersionTLS12)
	tlsConfig.InsecureSkipVerify = false // certificates and host names are checked
	transport.TLSClientConfig = tlsConfig
	return &http.Client{Timeout: 30 * time.Second, Transport: transport}, nil
}
