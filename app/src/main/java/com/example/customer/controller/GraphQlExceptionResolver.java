package com.example.customer.controller;

import com.example.customer.exception.ForbiddenWorkspaceAccessException;
import graphql.GraphQLError;
import graphql.GraphqlErrorBuilder;
import graphql.schema.DataFetchingEnvironment;
import org.springframework.graphql.execution.DataFetcherExceptionResolverAdapter;
import org.springframework.graphql.execution.ErrorType;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Component;

import java.util.NoSuchElementException;

/**
 * GlobalExceptionHandler (@RestControllerAdvice) does not apply here --
 * that mechanism is specific to Spring MVC's REST dispatch, and GraphQL
 * requests execute through a completely separate engine (graphql-java)
 * that never goes through DispatcherServlet's normal exception handling.
 * A DataFetcherExceptionResolver is GraphQL's own equivalent: it converts
 * an exception thrown by any resolver into a proper GraphQL error object
 * (with a real classification/error code) instead of either leaking a
 * raw stack trace or silently returning null.
 */
@Component
public class GraphQlExceptionResolver extends DataFetcherExceptionResolverAdapter {

    @Override
    protected GraphQLError resolveToSingleError(Throwable ex, DataFetchingEnvironment env) {
        if (ex instanceof NoSuchElementException) {
            return buildError(ex, env, ErrorType.NOT_FOUND);
        }
        if (ex instanceof ForbiddenWorkspaceAccessException || ex instanceof AccessDeniedException) {
            return buildError(ex, env, ErrorType.FORBIDDEN);
        }
        return null; // not one of ours -- let the default handling apply
    }

    private static GraphQLError buildError(Throwable ex, DataFetchingEnvironment env, ErrorType errorType) {
        return GraphqlErrorBuilder.newError(env)
                .message(ex.getMessage())
                .errorType(errorType)
                .build();
    }
}
