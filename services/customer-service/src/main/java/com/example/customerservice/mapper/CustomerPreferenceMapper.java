package com.example.customerservice.mapper;

import com.example.customerservice.dto.CustomerPreferenceResponse;
import com.example.customerservice.model.CustomerPreference;
import org.mapstruct.Mapper;

/**
 * BL-037: real MapStruct example, first use in this codebase -- confirmed
 * real NRG hands-on tool (context/CAREER_HISTORY.md's technical-stack list,
 * private career-context repo). Replaces
 * CustomerPreferenceResponse's hand-written static {@code from()} factory,
 * which is now deleted (no longer called anywhere, confirmed via a real
 * repo-wide grep before removing it) rather than left as unused dead code.
 *
 * componentModel = "spring": MapStruct generates a real @Component-
 * annotated implementation, constructor-injectable like any other Spring
 * bean -- the idiomatic choice for a Spring Boot codebase, over the
 * static Mappers.getMapper(...) singleton pattern used outside Spring.
 *
 * MapStruct's real code-generation targets a Java record's canonical
 * constructor by matching field names to record component names
 * (verified via the real generated source at target/generated-sources/
 * annotations/.../CustomerPreferenceMapperImpl.java after a real build --
 * grounding the claim, not assuming MapStruct's record support works a
 * particular way from memory).
 */
@Mapper(componentModel = "spring")
public interface CustomerPreferenceMapper {

    CustomerPreferenceResponse toResponse(CustomerPreference preference);
}
