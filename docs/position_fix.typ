= Timing

Satellite $k$

Receiver $i$

Transit time is $tau^k_i$

Pseudorange $P^k_i\/c = tau^k_i = t_i - t^k$

GPS time epoch is $t^"GPS"$

Clock offsets:

$t_i = t^"GPS" + d t_i$

$t^k = (t_i - tau^k_i)^"GPS" + d t^k$

Clock adjustment from ephem: $(t_i - tau^k_i)^"GPS" = t^k - (a_0 + a_1 (t^k - t_"oe" + ...))$

$t^k = t_i - P^k_i\/c$

$t_i$ is given, receiver's estimate of time

Pseudorange is observable

$t^k = t_"common" - d t^k$

= Position

Pseudorange:

$ P^k_i = rho^k_i + c (d t_i - d t^k) + T^k_i + I^k_i + e^k_i $

- $rho^k_i$ is geometric range
- $d t_i$ is receiver clock offset
- $d t^k$ is satellite clock offset
- $T^k_i$ is tropospheric delay
- $I^k_i$ is ionospheric delay
- $e^k_i$ is observation error

Geometric range:

$ rho^k_i = ||arrow(r)^k - arrow(r)_i|| $

- $arrow(r)^k$ is satellite position
- $arrow(r)_i$ is receiver position

== Linearize

Initial guess of $arrow(r)_(i, 0) = vec(0, 0, 0)$

Increment $arrow(r)_(i, 1) = arrow(r)_(i, 0) + Delta arrow(r)$

Least square format:

$ A bold(x) = mat(-(X^1 - X_(i, 0))/rho^1_(i, 0), -(Y^1 - Y_(i, 0))/rho^1_(i, 0), -(Z^1 - Z_(i, 0))/rho^1_(i, 0), 1; ...) vec(Delta X, Delta Y, Delta Z, c d t) = bold(b) - bold(e) $\
