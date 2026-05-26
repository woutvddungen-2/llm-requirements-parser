# Prompt Tuning Research Summary
## May 26, 2026

### Objective
Fine-tune prompts and PDF page extraction to improve pass rates on two challenging test cases:
- **Test 051**: Simple external door access control requirements (kaartlezer, elektrisch slot, noodknop)
- **Test 052**: Complex boundary door spatial reasoning (open/closed section intercom placement)

### Key Findings

#### Test 051 (Simple External Door Requirements)
**Challenge**: Models weren't extracting all required fields when information was spread across multiple sections of the PDF.

**Root Cause Analysis**:
1. **Cross-sentence component linkage issue**: When a component list ("kaartlezers, elektrische sloten, deurcontrole eenheden") appears before target door specification ("De toegangsdeuren krijgen een kaartlezer en nooddrukknop"), models need explicit instruction to apply ALL components to the target, not just explicitly mentioned ones.

2. **Conflicting section descriptions**: The PDF has multiple descriptions of the same doors:
   - Section 65.5 (Access Control): Comprehensive specification ("kaartlezer, elektrisch slot, noodknop, deurcontact")
   - Section 65.4.1 (Intrusion Detection): Generic specification ("buitendeur met deurcontact")
   - Models sometimes choose the simpler description over the comprehensive one.

3. **External door field requirements**: External doors (is_external: true) need `connects_to_areas: ["OUTSIDE"]` even when door_id is known, unlike internal doors.

**Prompt Improvements Made**:
- Added explicit component list handling instruction to `system_core.txt`
- Clarified that "elektrische sloten" → lock_type = SOLENOID_LOCK must be carried forward in cross-sentence linkage
- Clarified that "deurcontrole eenheden" → door_sensor = true must be carried forward
- Updated `logic_rules.txt` to explicitly state: "When access-control section explicitly lists components and target doors, use ONLY those fields. Do NOT supplement with fields from other sections."
- Updated examples in `examples_access_control.txt` to show correct field combinations for external doors

**Results**:
- Partial success: Easier when component list is immediately followed by target door sentence
- Still problematic when PDF has conflicting descriptions from multiple sections
- Models struggle with prioritizing the right section when both provide information

#### Test 052 (Boundary Door Spatial Reasoning)
**Challenge**: Determining which physical door should receive an intercom when description is ambiguous ("in het open gedeelte naast de abonnementdeur in de scheiding tussen open en gesloten").

**Root Cause Analysis**:
1. **Ambiguous spatial references**: Text mentions both location ("in het open gedeelte"/in the open part) AND spatial relationship ("in de scheiding"/in the boundary)
2. **Boundary door resolution**: Requires understanding that "scheiding" (division/boundary) takes precedence over first-mentioned location
3. **Complex enumeration**: With 6 doors and multiple spatial descriptions, models need to correctly map each specification to the right physical door

**Analysis**:
- All tested models (Anthropic Sonnet/Haiku, OpenAI, DeepSeek, Gemini) fail this test
- Not due to context limitations (all models have sufficient context)
- Not due to lack of examples (examples don't help much)
- Core issue: Requires genuine spatial reasoning beyond pattern matching

**Conclusion**: This test represents a fundamental limitation in current LLM reasoning capabilities for complex spatial boundary logic.

### Prompt Tuning Complexity Challenges

1. **Rule Interactions**: Adding guidance for one case (e.g., component linkage) can interfere with other cases (e.g., boundary door resolution). Rules can conflict:
   - Instruction: "Carry forward ALL components from component list"
   - Problem: Can cause over-extraction to doors not in the target sentence
   - Solution required: More nuanced scoping

2. **Reconciling Conflicting Descriptions**: When a door appears in multiple PDF sections with different properties:
   - Current approach: Hope the right section is selected
   - Better approach: Explicit hierarchy ("Access-control section is authoritative, ignore intrusion-detection generic description")
   - Challenge: Requires section detection which models struggle with

3. **External vs Internal Door Rules**: Different rules apply:
   - External: ALWAYS set `connects_to_areas=["OUTSIDE"]`
   - Internal: NEVER set `connects_to_areas` with door_id
   - Problem: Rules must be stated clearly and consistently across all prompt files

### Prompt Files Modified
1. **prompts/system_core.txt**: Added explicit component list handling and external/internal door rules
2. **prompts/logic_rules.txt**: Clarified cross-sentence component linkage and section precedence
3. **prompts/access_control/examples_access_control.txt**: Updated to show connects_to_areas for external doors
4. **src/prompt_builder.py**: Clarified connects_to_areas rules in door context section

### Lessons Learned

1. **Prompt Precision vs Completeness**: Very specific instructions for one scenario can break others. Balancing act between:
   - Being explicit enough to guide models correctly
   - Being general enough to not over-constrain other scenarios

2. **PDF Structure Awareness**: Models need guidance about which sections are authoritative when conflicts exist. Simple approach: "Access-control section is authoritative" helps, but detecting sections is hard.

3. **Spatial Reasoning Limits**: Some tasks (boundary door spatial mapping) may be fundamentally beyond current LLM capabilities, not fixable through prompt engineering.

4. **Cross-Section Component Linkage**: This is solvable but requires careful scoping to avoid false positives.

5. **Iterative Tuning Risk**: Small prompt changes can have unexpected interactions. Need:
   - Comprehensive test suite to catch regressions
   - Careful validation after each change
   - Clear rollback plan if changes break other cases

### Recommendations

**For Test 051 (Simple Requirements)**:
- Model selection matters more than prompt tuning
- Sonnet and DeepSeek handle component linkage better than Haiku/OpenAI
- If tuning further: Focus on section detection and hierarchy rather than broader rules

**For Test 052 (Boundary Doors)**:
- Not recommended to spend more effort on prompt tuning
- Consider acceptance testing rather than automated validation
- Alternative: Use simpler test case focusing on straightforward door mapping

**For Future Work**:
1. **Section Detection**: Add preprocessing step to identify which section each requirement comes from
2. **Rule Hierarchy**: Explicitly code precedence ("if in access-control section, ignore intrusion-detection information")
3. **Spatial Context**: Provide visual or structured representation of door topology before requirement text
4. **Few-Shot Examples**: More examples of boundary door resolution (current examples don't help much)
5. **Model-Specific Tuning**: Accept that different models need different prompts (Sonnet vs Haiku behave differently)

### Conclusion
Prompt engineering has limits. Test 051 can be partially improved through careful prompt specification, but Test 052 represents a spatial reasoning capability that current models struggle with regardless of prompt quality.  Further improvements likely require:
1. Better training data with spatial examples
2. Architectural changes to handle spatial relationships better
3. Hybrid approaches combining structured reasoning with LLMs
