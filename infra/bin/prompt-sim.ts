#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";

import { PromptSimilarityStack } from "../lib/prompt-similarity-stack";

const app = new cdk.App();

new PromptSimilarityStack(app, "PromptSimilarityStack", {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION ?? process.env.AWS_REGION ?? "us-east-1",
  },
});
