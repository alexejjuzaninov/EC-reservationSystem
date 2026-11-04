package com.ec.reservation;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
public class PreviewReadOnlyFilter extends OncePerRequestFilter {
    @Value("${app.preview.read-only:false}") private boolean readOnly;

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String path = request.getRequestURI();
        String method = request.getMethod();
        boolean safeBatch = "POST".equals(method) && "/api/stations/availability-batch".equals(path);
        if (readOnly && path.startsWith("/api/") && !("GET".equals(method) || "HEAD".equals(method) || safeBatch)) {
            response.setStatus(HttpServletResponse.SC_FORBIDDEN);
            response.setContentType("application/json");
            response.getWriter().write("{\"error\":\"Public preview is read-only. Data cannot be changed.\"}");
            return;
        }
        chain.doFilter(request, response);
    }
}
