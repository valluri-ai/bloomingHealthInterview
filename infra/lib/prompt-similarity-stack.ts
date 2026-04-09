import * as path from "path";

import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as ecrAssets from "aws-cdk-lib/aws-ecr-assets";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as efs from "aws-cdk-lib/aws-efs";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as iam from "aws-cdk-lib/aws-iam";
import * as logs from "aws-cdk-lib/aws-logs";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import { Construct } from "constructs";

export class PromptSimilarityStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const openAiApiKey = new cdk.CfnParameter(this, "OpenAiApiKey", {
      type: "String",
      noEcho: true,
      description: "OpenAI API key for embeddings and merge analysis.",
    });

    const vpc = new ec2.Vpc(this, "Vpc", {
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: [
        {
          name: "Public",
          subnetType: ec2.SubnetType.PUBLIC,
          cidrMask: 24,
        },
      ],
    });

    const cluster = new ecs.Cluster(this, "Cluster", {
      vpc,
      defaultCloudMapNamespace: {
        name: "prompt-sim.local",
        vpc,
      },
    });

    const promptBucket = new s3.Bucket(this, "PromptBucket", {
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      autoDeleteObjects: false,
    });

    const openAiSecret = new secretsmanager.Secret(this, "OpenAiApiKeySecret", {
      secretStringValue: cdk.SecretValue.unsafePlainText(openAiApiKey.valueAsString),
    });

    const neo4jSecret = new secretsmanager.Secret(this, "Neo4jPasswordSecret", {
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ username: "neo4j" }),
        generateStringKey: "password",
        excludePunctuation: true,
      },
    });
    const neo4jPassword = neo4jSecret.secretValueFromJson("password").toString();

    const neo4jFileSystem = new efs.FileSystem(this, "Neo4jFileSystem", {
      vpc,
      encrypted: true,
      performanceMode: efs.PerformanceMode.GENERAL_PURPOSE,
      throughputMode: efs.ThroughputMode.BURSTING,
      lifecyclePolicy: efs.LifecyclePolicy.AFTER_14_DAYS,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
    });
    const neo4jAccessPoint = neo4jFileSystem.addAccessPoint("Neo4jAccessPoint", {
      path: "/neo4j",
      createAcl: {
        ownerGid: "7474",
        ownerUid: "7474",
        permissions: "750",
      },
      posixUser: {
        gid: "7474",
        uid: "7474",
      },
    });

    const albSecurityGroup = new ec2.SecurityGroup(this, "AlbSecurityGroup", {
      vpc,
      allowAllOutbound: true,
      description: "Public ALB security group",
    });
    albSecurityGroup.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(80), "Allow public HTTP");

    const frontendSecurityGroup = new ec2.SecurityGroup(this, "FrontendSecurityGroup", {
      vpc,
      allowAllOutbound: true,
      description: "Frontend task security group",
    });
    frontendSecurityGroup.addIngressRule(albSecurityGroup, ec2.Port.tcp(3000), "Allow ALB to frontend");

    const backendSecurityGroup = new ec2.SecurityGroup(this, "BackendSecurityGroup", {
      vpc,
      allowAllOutbound: true,
      description: "Backend task security group",
    });
    backendSecurityGroup.addIngressRule(albSecurityGroup, ec2.Port.tcp(8000), "Allow ALB to backend");

    const neo4jSecurityGroup = new ec2.SecurityGroup(this, "Neo4jSecurityGroup", {
      vpc,
      allowAllOutbound: true,
      description: "Neo4j task security group",
    });
    neo4jSecurityGroup.addIngressRule(backendSecurityGroup, ec2.Port.tcp(7687), "Allow backend to Neo4j");
    neo4jFileSystem.connections.allowDefaultPortFrom(neo4jSecurityGroup, "Allow Neo4j task to mount EFS");

    const backendImage = ecs.ContainerImage.fromDockerImageAsset(
      new ecrAssets.DockerImageAsset(this, "BackendImage", {
        directory: path.resolve(__dirname, "../.."),
        file: "Dockerfile.backend",
        platform: ecrAssets.Platform.LINUX_ARM64,
      }),
    );

    const frontendImage = ecs.ContainerImage.fromDockerImageAsset(
      new ecrAssets.DockerImageAsset(this, "FrontendImage", {
        directory: path.resolve(__dirname, "../../web"),
        file: "Dockerfile",
        platform: ecrAssets.Platform.LINUX_ARM64,
      }),
    );

    const neo4jTaskDefinition = new ecs.FargateTaskDefinition(this, "Neo4jTaskDefinition", {
      cpu: 1024,
      memoryLimitMiB: 2048,
      runtimePlatform: {
        cpuArchitecture: ecs.CpuArchitecture.ARM64,
        operatingSystemFamily: ecs.OperatingSystemFamily.LINUX,
      },
      volumes: [
        {
          name: "neo4j-data",
          efsVolumeConfiguration: {
            fileSystemId: neo4jFileSystem.fileSystemId,
            transitEncryption: "ENABLED",
            authorizationConfig: {
              accessPointId: neo4jAccessPoint.accessPointId,
              iam: "ENABLED",
            },
          },
        },
      ],
    });
    const neo4jLogs = new logs.LogGroup(this, "Neo4jLogs", {
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
    const neo4jContainer = neo4jTaskDefinition.addContainer("Neo4jContainer", {
      image: ecs.ContainerImage.fromRegistry("neo4j:5.26-community"),
      logging: ecs.LogDrivers.awsLogs({ logGroup: neo4jLogs, streamPrefix: "neo4j" }),
      environment: {
        NEO4J_AUTH: cdk.Fn.join("", ["neo4j/", neo4jPassword]),
        NEO4J_server_memory_heap_initial__size: "512m",
        NEO4J_server_memory_heap_max__size: "1024m",
        NEO4J_server_memory_pagecache_size: "512m",
      },
      portMappings: [{ containerPort: 7687 }],
    });
    neo4jContainer.addMountPoints({
      sourceVolume: "neo4j-data",
      containerPath: "/data",
      readOnly: false,
    });
    neo4jFileSystem.grant(neo4jTaskDefinition.taskRole, "elasticfilesystem:ClientMount", "elasticfilesystem:ClientWrite", "elasticfilesystem:ClientRootAccess");

    const backendTaskDefinition = new ecs.FargateTaskDefinition(this, "BackendTaskDefinition", {
      cpu: 1024,
      memoryLimitMiB: 2048,
      runtimePlatform: {
        cpuArchitecture: ecs.CpuArchitecture.ARM64,
        operatingSystemFamily: ecs.OperatingSystemFamily.LINUX,
      },
    });
    const backendLogs = new logs.LogGroup(this, "BackendLogs", {
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
    backendTaskDefinition.addContainer("BackendContainer", {
      image: backendImage,
      logging: ecs.LogDrivers.awsLogs({ logGroup: backendLogs, streamPrefix: "backend" }),
      environment: {
        AWS_REGION: this.region,
        EMBEDDING_PROVIDER: "openai",
        EMBEDDING_MODEL: "text-embedding-3-large",
        MERGE_ANALYSIS_MODEL: "openai:gpt-4o-mini",
        BENCHMARK_DATASET_PATH: "/app/tmp/benchmark-dataset-1000.json",
        PROMPT_S3_BUCKET: promptBucket.bucketName,
        PROMPT_S3_PREFIX: "prompts",
        NEO4J_URI: "bolt://neo4j.prompt-sim.local:7687",
        NEO4J_USERNAME: "neo4j",
        NEO4J_DATABASE: "neo4j",
      },
      secrets: {
        OPENAI_API_KEY: ecs.Secret.fromSecretsManager(openAiSecret),
        NEO4J_PASSWORD: ecs.Secret.fromSecretsManager(neo4jSecret, "password"),
      },
      portMappings: [{ containerPort: 8000 }],
    });
    promptBucket.grantReadWrite(backendTaskDefinition.taskRole);
    openAiSecret.grantRead(backendTaskDefinition.executionRole!);
    neo4jSecret.grantRead(backendTaskDefinition.executionRole!);

    const frontendTaskDefinition = new ecs.FargateTaskDefinition(this, "FrontendTaskDefinition", {
      cpu: 256,
      memoryLimitMiB: 512,
      runtimePlatform: {
        cpuArchitecture: ecs.CpuArchitecture.ARM64,
        operatingSystemFamily: ecs.OperatingSystemFamily.LINUX,
      },
    });
    const frontendLogs = new logs.LogGroup(this, "FrontendLogs", {
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
    frontendTaskDefinition.addContainer("FrontendContainer", {
      image: frontendImage,
      logging: ecs.LogDrivers.awsLogs({ logGroup: frontendLogs, streamPrefix: "frontend" }),
      environment: {
        NODE_ENV: "production",
      },
      portMappings: [{ containerPort: 3000 }],
    });

    const neo4jService = new ecs.FargateService(this, "Neo4jService", {
      cluster,
      taskDefinition: neo4jTaskDefinition,
      desiredCount: 1,
      assignPublicIp: true,
      securityGroups: [neo4jSecurityGroup],
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      cloudMapOptions: {
        name: "neo4j",
      },
    });
    neo4jService.connections.allowFrom(backendSecurityGroup, ec2.Port.tcp(7687), "Allow backend to reach Neo4j");

    const backendService = new ecs.FargateService(this, "BackendService", {
      cluster,
      taskDefinition: backendTaskDefinition,
      desiredCount: 1,
      assignPublicIp: true,
      securityGroups: [backendSecurityGroup],
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
    });

    const frontendService = new ecs.FargateService(this, "FrontendService", {
      cluster,
      taskDefinition: frontendTaskDefinition,
      desiredCount: 1,
      assignPublicIp: true,
      securityGroups: [frontendSecurityGroup],
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
    });

    const loadBalancer = new elbv2.ApplicationLoadBalancer(this, "LoadBalancer", {
      vpc,
      internetFacing: true,
      securityGroup: albSecurityGroup,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
    });
    loadBalancer.setAttribute("idle_timeout.timeout_seconds", "300");

    const frontendTargetGroup = new elbv2.ApplicationTargetGroup(this, "FrontendTargetGroup", {
      vpc,
      port: 3000,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targetType: elbv2.TargetType.IP,
      healthCheck: {
        enabled: true,
        path: "/",
        healthyHttpCodes: "200-399",
        interval: cdk.Duration.seconds(30),
      },
    });
    frontendService.attachToApplicationTargetGroup(frontendTargetGroup);

    const backendTargetGroup = new elbv2.ApplicationTargetGroup(this, "BackendTargetGroup", {
      vpc,
      port: 8000,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targetType: elbv2.TargetType.IP,
      healthCheck: {
        enabled: true,
        path: "/health",
        healthyHttpCodes: "200",
        interval: cdk.Duration.seconds(30),
      },
    });
    backendService.attachToApplicationTargetGroup(backendTargetGroup);

    const listener = loadBalancer.addListener("HttpListener", {
      port: 80,
      open: true,
      defaultTargetGroups: [frontendTargetGroup],
    });
    listener.addTargetGroups("BackendApiPaths", {
      priority: 10,
      conditions: [elbv2.ListenerCondition.pathPatterns(["/api/*"])],
      targetGroups: [backendTargetGroup],
    });

    new cdk.CfnOutput(this, "AppUrl", {
      value: `http://${loadBalancer.loadBalancerDnsName}`,
    });
    new cdk.CfnOutput(this, "PromptBucketName", {
      value: promptBucket.bucketName,
    });
    new cdk.CfnOutput(this, "Neo4jServiceHost", {
      value: "neo4j.prompt-sim.local",
    });
  }
}
