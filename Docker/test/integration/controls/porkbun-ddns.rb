title "Porkbun-DDNS Integration Test"

describe processes(Regexp.new("python")) do
  it { should exist }
  its('users') { should include 'root' }
  its('pids') { should cmp "1"}
end
