# Safety and legality checklist

Before merging:

- [ ] RoE profile is required or safe default is used
- [ ] LLM cannot expand scope
- [ ] LLM cannot change target host
- [ ] LLM cannot call arbitrary tools
- [ ] LLM cannot run shell commands
- [ ] LLM cannot access local files
- [ ] LLM cannot access private IPs unless RoE allows it
- [ ] redirects cannot leave scope
- [ ] disallowed methods are blocked
- [ ] disallowed test categories are blocked
- [ ] brute force is blocked unless RoE allows it
- [ ] rate-limit testing is blocked unless RoE allows it
