# Kubernetes Network Checker

A lightweight network connectivity dashboard for Kubernetes clusters.

## Features

- Check TCP connectivity from every worker node
- Parallel connectivity test
- Web Dashboard
- ConfigMap based node discovery
- nc (netcat) connectivity validation

해당 페이지에서 전체 노드 방화벽 점검이 가능함
※ 필요한 사항
- configmap에 워커노드 정보를 추가해야함

- svc 생성 시 필요한 세팅값
externalTrafficPolicy: Local

- daemonset 생성 시 필요한 세팅값
spec:
      hostNetwork: true
      containers:
      - name: web-ui-agent
        image: python:3.10-slim
        env:
        - name: NODE_NAME
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName
        - name: NODE_IP
          valueFrom:
            fieldRef:
              fieldPath: status.hostIP
        command: ["/bin/sh", "-c"]
